import datetime
import os
import platform
import subprocess
import time
import json
import uuid
import requests
import hashlib
from typing import Dict

# NOTE: The default API_ENDPOINT uses HTTP for local testing.
# For production, change this to an HTTPS endpoint to avoid the secure transmission error in run_agent.
API_ENDPOINT = "http://127.0.0.1:8000/api/report"
CACHE_FILE = "./agent/agent_cache.json"
INTERVAL_MINUTES = 30 # Interval between checks, in minutes

# GUIDs used to access sleep task in Windows power plans
SUBGROUP_GUID = "238c9fa8-0aad-41ed-83f4-97be242c8f20"
SETTING_GUID = "29f6c1db-86da-48c5-9fdb-f2b67b1f44da"

class SystemUtility:
    """
    Utility class for collecting system health and configuration information.
    Supports Windows, macOS (Darwin), and Linux.
    """
    def __init__(self):
        self.platform = platform.system()

    def _run(self, command, shell=False):
        """
        Helper to run a shell command and return its output as a string.
        """
        try:
            return subprocess.check_output(
                command,
                text=True,
                shell=shell,
                stderr=subprocess.DEVNULL
            )
        except Exception as e:
            print(f"[ERROR] Failed to run command: {e}")

    def check_disk_encryption(self) -> bool:
        """
        Check if the system disk is fully encrypted.
        """
        if self.platform == "Windows":
            out = self._run(["manage-bde", "-status", "C:"])
            return ("Percentage Encrypted: 100%" in out) if out else False
        elif self.platform == "Darwin":
            out = self._run(["fdesetup", "status"])
            return ("FileVault is On" in out) if out else False # type: ignore
        elif self.platform == "Linux":
            out = self._run(["lsblk", "-no", "TYPE"])
            return "crypt" in out.splitlines() if out else False
        return False

    def check_os_updates_pending(self) -> bool:
        """
        Check if there are pending OS updates.
        """
        if self.platform == "Windows":
            cmd = [
                "powershell", "-Command",
                "(New-Object -ComObject Microsoft.Update.Session).CreateUpdateSearcher().Search('IsInstalled=0').Updates.Count"
            ]
            out = self._run(cmd)
            return bool(out and out.strip().isdigit())
        elif self.platform == "Darwin":
            out = self._run(["softwareupdate", "-l"])
            return (out.count("\n   *") > 0) if out else False
        elif self.platform == "Linux":
            self._run(["apt", "update"])
            out = self._run(["apt", "list", "--upgradable"])
            return bool(max(0, len(out.splitlines()) - 1) if out else None)
        return False

    def check_antivirus_status(self) -> bool:
        """
        Check if an antivirus product is active.
        """
        if self.platform == "Windows":
            out = self._run([
                "powershell",
                "-Command",
                (
                    "Get-CimInstance -Namespace root/SecurityCenter2 "
                    "-ClassName AntivirusProduct | "
                    "Select-Object -ExpandProperty displayName"
                )
            ])
            return bool(out)
        elif self.platform == "Darwin":
            out = self._run("pgrep -l clam|sav|intego|symantec", shell=True)
            return bool(out.strip()) if out else False
        elif self.platform == "Linux":
            out = self._run("pgrep -l clamd|freshclam", shell=True)
            return bool(out.strip()) if out else False
        return False

    def check_sleep_timeout(self) -> int:
        """
        Get the system sleep timeout in minutes.
        Returns -1 if unable to determine.
        """
        if self.platform == "Windows":
            # Get the active power scheme GUID
            active_scheme = self._run(["powercfg", "/GETACTIVESCHEME"]).split(":")[1].strip().split(" ")[0] # type: ignore
            out = self._run(["powercfg", "-Q",  active_scheme, SUBGROUP_GUID, SETTING_GUID])
            if out:
                import re
                m = re.search(r"Current DC Power Setting Index:\s*0x([0-9A-Fa-f]+)", out)
                timeout = int(m.group(1), 16) // 60 if m else -1
                return timeout
        elif self.platform == "Darwin":
            out = self._run(["systemsetup", "-getcomputersleep"])
            timeout = int(out.split()[-2]) if out else -1
            return timeout
        elif self.platform == "Linux":
            out = self._run(["gsettings", "get", "org.gnome.desktop.session", "idle-delay"])
            timeout = int(out.strip()) // 60 if out and out.strip().isdigit() else -1
            return timeout
        return -1

    def collect_state(self) -> Dict:
        """
        Collect the current system state as a dictionary.
        """
        return {
            "machine_id": str(uuid.getnode()),
            "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "platform": self.platform,
            "disk_encrypted": self.check_disk_encryption(),
            "os_updates_pending": self.check_os_updates_pending(),
            "antivirus_active": self.check_antivirus_status(),
            "sleep_timeout_min": self.check_sleep_timeout(),
        }

def hash_state(state: dict) -> str:
    """
    Generate a consistent hash for a system state dict.
    Ignores non-essential fields like timestamp.
    """
    state_no_timestamp = {k: v for k, v in state.items() if k != "timestamp"}
    state_json = json.dumps(state_no_timestamp, sort_keys=True)
    return hashlib.sha256(state_json.encode()).hexdigest()

def send_to_api(state: Dict, endpoint: str):
    """
    Send the collected state to the specified API endpoint.
    """
    try:
        r = requests.post(endpoint, json=state, timeout=5)
        r.raise_for_status()
        print(f"[{state['timestamp']}] Data sent.")
    except Exception as e:
        print(f"[{state['timestamp']}] Failed to send: {e}")

def has_state_changed(new_state: dict) -> bool:
    """
    Check if the system state has changed since the last check.
    Uses a hash of the state (excluding timestamp) and stores it in a cache file.
    """
    h = hash_state(new_state)
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE) as f:
                old_data = json.load(f)
            if old_data.get("hash") == h:
                return False
        except:
            pass
    # Ensure the directory exists before writing
    os.makedirs(os.path.dirname(CACHE_FILE), exist_ok=True)
    with open(CACHE_FILE, "w") as f:
        json.dump({"hash": h}, f)
    return True

def run_agent(endpoint: str, interval_minutes: int = 30):
    """
    Main loop for the agent.
    Collects system state, checks for changes, and sends updates to the API endpoint.
    """
    if not endpoint.lower().startswith("https://"):
        raise ValueError("[ERROR]Insecure API endpoint. HTTPS is required for secure transmission.")

    util = SystemUtility()

    while True:
        print("[INFO] Collecting system state...")
        current_state = util.collect_state()
        print("[DEBUG] State collected:", current_state)

        if has_state_changed(current_state):
            print("[INFO] State has changed!")
            send_to_api(current_state, endpoint)
        print(f"[INFO] Sleeping for {interval_minutes} min...\n")
        time.sleep(interval_minutes * 60)

if __name__ == "__main__":
    try:    
        run_agent(API_ENDPOINT, INTERVAL_MINUTES)
    except KeyboardInterrupt:
        print("\n[INFO] Agent stopped by user.")
