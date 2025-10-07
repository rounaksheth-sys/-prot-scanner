import socket
import threading
from queue import Queue
import csv
from datetime import datetime

# Try colorama
try:
    from colorama import init, Fore, Style # pyright: ignore[reportMissingModuleSource]
    init(autoreset=True)
except Exception:
    class _C:
        GREEN = ''
        RED = ''
        RESET_ALL = ''
    Fore = _C()
    Style = _C()

# Beginner-tweakable settings
threads_count = 50   # increase to scan faster (but don't overwhelm target)
timeout = 0.5        # socket timeout in seconds

# Short list of common ports -> service name
COMMON_PORTS = {
    20: "FTP-data",
    21: "FTP-control",
    22: "SSH",
    23: "Telnet",
    25: "SMTP",
    53: "DNS",
    67: "DHCP",
    69: "TFTP",
    80: "HTTP",
    110: "POP3",
    123: "NTP",
    139: "NetBIOS",
    143: "IMAP",
    161: "SNMP",
    194: "IRC",
    443: "HTTPS",
    445: "SMB",
    587: "SMTP (submission)",
    631: "IPP",
    993: "IMAPS",
    995: "POP3S",
    1433: "MSSQL",
    1521: "Oracle",
    2049: "NFS",
    3306: "MySQL",
    3389: "RDP",
    5432: "PostgreSQL",
    5900: "VNC",
    6379: "Redis",
    8080: "HTTP-alt",
}

q = Queue()
csv_lock = threading.Lock()
print_lock = threading.Lock()
open_ports = []
stop_signal = object()

def scan_port(host, port):
    """Return True if port open, False otherwise."""
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(timeout)
    try:
        return s.connect_ex((host, port)) == 0
    except Exception:
        return False
    finally:
        s.close()

def worker(host, csv_writer, save_csv):
    while True:
        item = q.get()
        if item is stop_signal:
            q.task_done()
            break
        port = item
        is_open = scan_port(host, port)
        service = COMMON_PORTS.get(port, "")
        status = "OPEN" if is_open else "CLOSED"
        timestamp = datetime.now().isoformat(timespec="seconds")

        # Thread-safe printing
        with print_lock:
            if is_open:
                print(f"{Fore.GREEN}[OPEN]   Port {port:5} {service}{Style.RESET_ALL}", flush=True)
                open_ports.append(port)
            else:
                print(f"{Fore.RED}[CLOSED] Port {port:5} {service}{Style.RESET_ALL}", flush=True)

        # Write to CSV if requested
        if save_csv and csv_writer is not None:
            with csv_lock:
                csv_writer.writerow([timestamp, host, port, service, status])

        q.task_done()

def main():
    print("Threaded Port Scanner — common ports option + optional CSV\n")
    host = input("Target (IP or hostname) [default: 127.0.0.1]: ").strip() or "127.0.0.1"

    mode = input("Scan common ports or range? (c/r) [default: c]: ").strip().lower() or "c"
    if mode == "r":
        port_range = input("Ports (start-end) [default: 1-1024]: ").strip() or "1-1024"
        try:
            start_s, end_s = port_range.split("-")
            start_port = int(start_s)
            end_port = int(end_s)
            if start_port < 1 or end_port > 65535 or start_port > end_port:
                raise ValueError
            ports = list(range(start_port, end_port + 1))
        except Exception:
            print("Invalid range. Falling back to common ports.")
            ports = sorted(COMMON_PORTS.keys())
    else:
        ports = sorted(COMMON_PORTS.keys())

    # Option to save CSV
    save_choice = input("Save results to CSV? (Y/n) [default: Y]: ").strip().lower()
    save_csv = (save_choice == "" or save_choice == "y" or save_choice == "yes")
    csv_name = None
    if save_csv:
        csv_name = input("CSV filename [default: scan_results.csv]: ").strip() or "scan_results.csv"

    # Summary before scanning
    print(f"\nScanning {host} {len(ports)} ports with {threads_count} threads (timeout {timeout}s)\n")
    if save_csv:
        print(f"Results will be saved to: {csv_name}\n")
    else:
        print("CSV saving disabled — results will be printed only.\n")

    # Open CSV if needed
    if save_csv:
        csv_file = open(csv_name, mode="w", newline="", encoding="utf-8")
        writer = csv.writer(csv_file)
        writer.writerow(["timestamp", "host", "port", "service", "status"])
    else:
        csv_file = None
        writer = None

    try:
        # start worker threads
        threads = []
        for _ in range(threads_count):
            t = threading.Thread(target=worker, args=(host, writer, save_csv), daemon=True)
            t.start()
            threads.append(t)

        # enqueue ports (use the list so order is predictable if desired)
        for port in ports:
            q.put(port)

        # wait until processing done
        q.join()

        # stop workers cleanly
        for _ in threads:
            q.put(stop_signal)
        q.join()

    finally:
        if csv_file:
            csv_file.close()

    # summary
    print("\nScan complete.")
    if open_ports:
        print(f"{Fore.GREEN}Open ports: {sorted(set(open_ports))}{Style.RESET_ALL}")
    else:
        print(f"{Fore.RED}No open ports found.{Style.RESET_ALL}")
    if save_csv:
        print(f"Saved results to: {csv_name}")
    else:
        print("No CSV file was written.")

if __name__ == "__main__":
    main()