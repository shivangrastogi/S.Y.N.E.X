import socket
import psutil

def find_my_ip():
    # Get all network interfaces and their addresses
    addrs = psutil.net_if_addrs()
    candidates = []

    for interface_name, interface_addresses in addrs.items():
        for addr in interface_addresses:
            # We only want IPv4 addresses, not loopback or link-local
            if addr.family == socket.AF_INET and not addr.address.startswith(("127.", "169.254.")):
                candidates.append((interface_name, addr.address))

    # Prefer Wi-Fi, then Ethernet
    wifi_ip = next((ip for name, ip in candidates if "wi-fi" in name.lower()), None)
    ethernet_ip = next((ip for name, ip in candidates if "ethernet" in name.lower()), None)

    # Fallback to first valid IP if no match found
    ip_to_use = wifi_ip or ethernet_ip or (candidates[0][1] if candidates else None)

    if ip_to_use:
        print(f"Your device IP address is: {ip_to_use}")
        return ip_to_use
    else:
        print("No active network interface found.")
        return None

if __name__ == "__main__":
    find_my_ip()
