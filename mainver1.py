import paramiko
import time
import os
import logging
import argparse
from datetime import datetime

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    filename=f'firmware_upgrade_test_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log'
)

class SwitchFirmwareUpgrader:
    def __init__(self, hostname, ip_address, username, password, model):
        self.hostname = hostname
        self.ip_address = ip_address
        self.username = username
        self.password = password
        self.model = model
        self.ssh_client = None
        
    def connect(self):
        """Establish SSH connection to the switch"""
        try:
            self.ssh_client = paramiko.SSHClient()
            self.ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            self.ssh_client.connect(
                hostname=self.ip_address,
                username=self.username,
                password=self.password,
                timeout=30
            )
            logging.info(f"Successfully connected to {self.hostname}")
            return True
        except Exception as e:
            logging.error(f"Failed to connect to {self.hostname}: {str(e)}")
            return False
            
    def disconnect(self):
        """Close SSH connection"""
        if self.ssh_client:
            self.ssh_client.close()
            self.ssh_client = None
            
    def execute_command(self, command):
        """Execute a command on the switch and return the output"""
        if not self.ssh_client:
            if not self.connect():
                return None
                
        try:
            stdin, stdout, stderr = self.ssh_client.exec_command(command)
            return stdout.read().decode('utf-8')
        except Exception as e:
            logging.error(f"Error executing command on {self.hostname}: {str(e)}")
            return None
            
    def get_current_version(self):
        """Get the current firmware version"""
        # This command varies by vendor - adjust as needed
        output = self.execute_command("show version")
        if not output:
            return None
            
        # This parsing logic will be vendor-specific
        # Example for Cisco: searching for "Version" in output
        for line in output.splitlines():
            if "Version" in line:
                version = line.split("Version")[1].strip().split()[0]
                logging.info(f"Current version on {self.hostname}: {version}")
                return version
                
        logging.error(f"Could not determine current version on {self.hostname}")
        return None
        
    def backup_config(self):
        """Backup the switch configuration"""
        output = self.execute_command("show running-config")
        if not output:
            return False
            
        backup_file = f"backup_{self.hostname}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        try:
            with open(backup_file, 'w') as f:
                f.write(output)
            logging.info(f"Configuration backed up to {backup_file}")
            return backup_file
        except Exception as e:
            logging.error(f"Failed to save backup: {str(e)}")
            return False
            
    def transfer_firmware(self, firmware_file, remote_path="/flash/"):
        """Transfer firmware file to the switch using SCP"""
        try:
            from scp import SCPClient
            
            if not self.ssh_client:
                if not self.connect():
                    return False
                    
            scp = SCPClient(self.ssh_client.get_transport())
            scp.put(firmware_file, remote_path=remote_path)
            scp.close()
            
            remote_file = f"{remote_path}{os.path.basename(firmware_file)}"
            logging.info(f"Firmware transferred to {self.hostname}:{remote_file}")
            return remote_file
        except Exception as e:
            logging.error(f"Failed to transfer firmware to {self.hostname}: {str(e)}")
            return False
            
    def install_firmware(self, remote_file):
        """Install the firmware on the switch"""
        # This command varies by vendor - adjust as needed
        command = f"install system {remote_file}"
        
        output = self.execute_command(command)
        if not output:
            return False
            
        logging.info(f"Firmware installation initiated on {self.hostname}")
        logging.info(f"Installation output: {output}")
        return True
        
    def verify_upgrade(self, target_version, max_retries=5, retry_delay=60):
        """Verify the firmware was successfully installed"""
        # Allow time for switch to reboot
        logging.info(f"Waiting for {self.hostname} to reboot...")
        time.sleep(300)  # 5 minutes
        
        retry_count = 0
        while retry_count < max_retries:
            try:
                if self.connect():
                    current_version = self.get_current_version()
                    if current_version == target_version:
                        logging.info(f"Upgrade successful: {self.hostname} is now running {current_version}")
                        return True
                    else:
                        logging.warning(f"Version mismatch: expected {target_version}, found {current_version}")
                        
                retry_count += 1
                logging.info(f"Retry {retry_count}/{max_retries}. Waiting {retry_delay} seconds...")
                time.sleep(retry_delay)
            finally:
                self.disconnect()
                
        logging.error(f"Failed to verify upgrade on {self.hostname} after {max_retries} attempts")
        return False
        
    def rollback(self, backup_file=None):
        """Roll back to previous firmware version"""
        if not self.connect():
            return False
            
        try:
            # Command to boot previous version (vendor-specific)
            output = self.execute_command("boot system previous")
            logging.info(f"Rollback command output: {output}")
            
            # Reboot the switch
            self.execute_command("reload in 1")
            logging.info(f"Reboot initiated on {self.hostname}")
            
            # If we have a backup file and need to restore it
            if backup_file and os.path.exists(backup_file):
                # Wait for reboot
                time.sleep(300)
                
                if not self.connect():
                    logging.error("Could not connect after reboot to restore configuration")
                    return False
                    
                # Read backup file
                with open(backup_file, 'r') as f:
                    config = f.read()
                    
                # Transfer config to switch (this approach varies by vendor)
                # This is a simplified example
                with self.ssh_client.invoke_shell() as shell:
                    shell.send("configure terminal\n")
                    time.sleep(1)
                    shell.send(config)
                    time.sleep(1)
                    shell.send("end\n")
                    time.sleep(1)
                    shell.send("write memory\n")
                    time.sleep(1)
                    
                logging.info(f"Configuration restored on {self.hostname}")
            
            return True
        except Exception as e:
            logging.error(f"Error during rollback: {str(e)}")
            return False
        finally:
            self.disconnect()
            
def parse_arguments():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(description='Switch Firmware Upgrade Tool')
    
    # Required arguments
    parser.add_argument('--hostname', required=True, help='Switch hostname')
    parser.add_argument('--ip', required=True, help='Switch IP address')
    parser.add_argument('--username', required=True, help='SSH username')
    parser.add_argument('--model', required=True, help='Switch model')
    
    # Optional arguments
    parser.add_argument('--password', help='SSH password (if not provided, will prompt)')
    parser.add_argument('--firmware', required=True, help='Path to firmware file')
    parser.add_argument('--target-version', required=True, help='Target firmware version')
    parser.add_argument('--remote-path', default='/flash/', help='Remote path to store firmware')
    parser.add_argument('--retry-count', type=int, default=5, help='Max retry attempts for verification')
    parser.add_argument('--retry-delay', type=int, default=60, help='Seconds between retry attempts')
    
    return parser.parse_args()

def main():
    # Parse command line arguments
    args = parse_arguments()
    
    # If password not provided via command line, prompt for it
    password = args.password
    if not password:
        import getpass
        password = getpass.getpass(f"Enter password for {args.username}@{args.ip}: ")
    
    # Initialize the upgrader
    upgrader = SwitchFirmwareUpgrader(
        args.hostname,
        args.ip,
        args.username,
        password,
        args.model
    )
    
    logging.info(f"Starting firmware upgrade test on {args.hostname}")
    
    try:
        # Step 1: Connect and check current version
        if not upgrader.connect():
            logging.error("Test failed: Could not connect to switch")
            return
            
        current_version = upgrader.get_current_version()
        upgrader.disconnect()
        
        if not current_version:
            logging.error("Test failed: Could not determine current version")
            return
            
        if current_version == args.target_version:
            logging.info(f"Switch already running target version {args.target_version}")
            return
            
        # Step 2: Backup configuration
        backup_file = upgrader.backup_config()
        if not backup_file:
            logging.error("Test failed: Could not backup configuration")
            return
            
        # Step 3: Transfer firmware
        remote_file = upgrader.transfer_firmware(args.firmware, args.remote_path)
        if not remote_file:
            logging.error("Test failed: Could not transfer firmware")
            return
            
        # Step 4: Install firmware
        if not upgrader.install_firmware(remote_file):
            logging.error("Test failed: Could not install firmware")
            # Try rollback
            upgrader.rollback(backup_file)
            return
            
        # Step 5: Verify upgrade
        if not upgrader.verify_upgrade(args.target_version, args.retry_count, args.retry_delay):
            logging.error("Test failed: Could not verify upgrade")
            # Try rollback
            upgrader.rollback(backup_file)
            return
            
        logging.info(f"Firmware upgrade test completed successfully on {args.hostname}")
        
    except Exception as e:
        logging.error(f"Unexpected error during upgrade test: {str(e)}")
        # Try rollback
        upgrader.rollback(backup_file)

if __name__ == "__main__":
    main()