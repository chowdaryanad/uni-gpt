import paramiko
import time
import sys

# Force stdout to use utf-8 to prevent charmap errors on Windows
sys.stdout.reconfigure(encoding='utf-8')

def run_command(ssh, command):
    print(f"\n============================================\nRunning: {command}")
    stdin, stdout, stderr = ssh.exec_command(command, get_pty=True)
    
    # We might need to send the password for sudo
    time.sleep(1)
    
    while not stdout.channel.exit_status_ready():
        if stdout.channel.recv_ready():
            print(stdout.channel.recv(1024).decode('utf-8', errors='replace'), end='')
        if stderr.channel.recv_ready():
            print(stderr.channel.recv(1024).decode('utf-8', errors='replace'), end='')
        time.sleep(0.1)

    print(stdout.read().decode('utf-8', errors='replace'))
    print(stderr.read().decode('utf-8', errors='replace'))
    print(f"Exit status: {stdout.channel.recv_exit_status()}")

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

try:
    print("Connecting...")
    ssh.connect('4.240.101.15', username='anand', password='Anand@123456', timeout=10)
    print("Connected!")
    
    print("Uploading .env file...")
    sftp = ssh.open_sftp()
    try:
        sftp.put('backend/.env', '/home/anand/uni-gpt/backend/.env')
        print("Uploaded .env file!")
    except Exception as e:
        print(f"Warning: Could not upload .env file: {e}")
    sftp.close()
    
    commands = [
        "cd uni-gpt && source venv/bin/activate && pip install -r requirements.txt",
        "cd uni-gpt/backend && ../venv/bin/python manage.py collectstatic --noinput",
        "cd uni-gpt/backend && ../venv/bin/python manage.py migrate",
        """echo 'Anand@123456' | sudo -S bash -c 'cat > /etc/systemd/system/unigpt.service <<EOF
[Unit]
Description=gunicorn daemon for unigpt
After=network.target

[Service]
User=anand
Group=www-data
WorkingDirectory=/home/anand/uni-gpt/backend
Environment="PATH=/home/anand/uni-gpt/venv/bin"
ExecStart=/home/anand/uni-gpt/venv/bin/gunicorn --access-logfile - --workers 2 --threads 3 --worker-class gthread --timeout 120 --bind 0.0.0.0:8000 config.wsgi:application

[Install]
WantedBy=multi-user.target
EOF'""",
        "echo 'Anand@123456' | sudo -S systemctl daemon-reload",
        "echo 'Anand@123456' | sudo -S systemctl start unigpt",
        "echo 'Anand@123456' | sudo -S systemctl enable unigpt",
        "echo 'Anand@123456' | sudo -S systemctl status unigpt --no-pager"
    ]
    
    for cmd in commands:
        run_command(ssh, cmd)
        
finally:
    ssh.close()
