# Deploying Zotta to AWS EC2 (Single Server)

This is the cheapest way to run Zotta on AWS. Everything runs on one small server using Docker Compose -- the same way it runs on your laptop, but accessible from the internet.

**Cost: ~$12-15/month when running, $0 when stopped.**

---

## Prerequisites

You need two things on your Mac before starting:

### 1. AWS CLI (talks to Amazon)

```bash
brew install awscli
```

Then configure it with your AWS credentials:

```bash
aws configure
```

It asks four questions:
- **AWS Access Key ID**: get this from AWS Console > your name > Security credentials > Create access key
- **AWS Secret Access Key**: shown when you create the key above
- **Default region**: `us-east-1`
- **Default output**: `json`

### 2. An AWS Account

Sign up at https://aws.amazon.com if you don't have one. You'll need a credit card.

---

## Deploy in 3 Steps

### Step 1: Launch the server

From your Mac Terminal:

```bash
cd ~/Downloads/Zotta/infrastructure/ec2
./launch-ec2.sh
```

This takes about 1 minute. It creates:
- A small server (t3.small: 2 CPU, 2 GB RAM)
- A firewall that allows web traffic (ports 80, 443) and SSH (port 22)
- An SSH key to connect to the server

When done, it prints something like:

```
  Instance ID:  i-0abc123def456
  Public IP:    54.123.45.67
  SSH Key:      ~/.ssh/zotta-key.pem
```

### Step 2: Connect to the server and set it up

Wait 30 seconds for the server to boot, then:

```bash
ssh -i ~/.ssh/zotta-key.pem ubuntu@54.123.45.67
```

(Replace `54.123.45.67` with your actual IP from Step 1)

You might see "Are you sure you want to continue connecting?" -- type `yes`.

Once connected, run:

```bash
curl -sSL https://raw.githubusercontent.com/energet52/Zotta/main/infrastructure/ec2/server-setup.sh | bash
```

This takes 3-5 minutes. It automatically:
- Installs Docker on the server
- Downloads the Zotta code from GitHub
- Generates secure passwords and secret keys
- Builds and starts all containers
- Seeds the database with test data

### Step 3: Open in your browser

Go to: `http://54.123.45.67` (your EC2 IP)

You should see the Zotta login page. Log in with:
- **Admin**: admin@zotta.tt / Admin123!
- **Applicant**: john.doe@email.com / Applicant1!

---

## Managing Your Server

### Connect via SSH

```bash
ssh -i ~/.ssh/zotta-key.pem ubuntu@YOUR_IP
```

### View logs

```bash
cd ~/Zotta
sudo docker compose -f docker-compose.prod.yml logs -f
```

### Restart the application

```bash
cd ~/Zotta
sudo docker compose -f docker-compose.prod.yml restart
```

### Update to the latest code

```bash
cd ~/Zotta
git pull
sudo docker compose -f docker-compose.prod.yml up -d --build
```

### Stop the application (keeps server running)

```bash
cd ~/Zotta
sudo docker compose -f docker-compose.prod.yml down
```

---

## Controlling Costs

### Stop the server (stop paying)

When you're not using Zotta, stop the EC2 instance. You stop paying for compute but keep your data.

From your Mac:
```bash
aws ec2 stop-instances --instance-ids i-0abc123def456
```

(Replace with your actual instance ID from Step 1)

**Cost when stopped: ~$1-2/month** (just the disk storage).

### Start it again

```bash
aws ec2 start-instances --instance-ids i-0abc123def456
```

**Important**: The public IP changes each time you stop/start. To see the new IP:
```bash
aws ec2 describe-instances --instance-ids i-0abc123def456 \
    --query 'Reservations[0].Instances[0].PublicIpAddress' --output text
```

### Get a fixed IP (optional, +$3.60/month when server is stopped)

If you want the IP to stay the same:
```bash
# Allocate a static IP
aws ec2 allocate-address --query 'AllocationId' --output text
# Returns: eipalloc-0abc123

# Attach it to your instance
aws ec2 associate-address --instance-id i-0abc123def456 --allocation-id eipalloc-0abc123
```

### Delete everything permanently

```bash
aws ec2 terminate-instances --instance-ids i-0abc123def456
```

This deletes the server and all data on it. Your code on GitHub is safe.

---

## Adding a Domain Name (optional)

If you own a domain (e.g., `zotta.tt`):

1. Go to your domain registrar (GoDaddy, Namecheap, etc.)
2. Add an **A record** pointing to your EC2 public IP:
   - Name: `@` (or `www`)
   - Type: A
   - Value: `54.123.45.67` (your IP)
3. Wait 5-30 minutes for DNS to update
4. Visit `http://zotta.tt`

---

## Adding HTTPS (optional)

Once you have a domain name, add free HTTPS with Let's Encrypt:

SSH into your server and run:
```bash
sudo apt-get install -y certbot
sudo certbot certonly --standalone -d yourdomain.com
```

Then update the nginx config to use the certificate. This is a more advanced step -- contact your developer if needed.

---

## Troubleshooting

### "Connection refused" when opening the IP in browser

The setup might still be running. SSH in and check:
```bash
sudo docker compose -f docker-compose.prod.yml ps
```

All services should show "Up". If not:
```bash
sudo docker compose -f docker-compose.prod.yml logs
```

### "Permission denied" when SSH-ing

Make sure you're using the right key and username:
```bash
ssh -i ~/.ssh/zotta-key.pem ubuntu@YOUR_IP
```

Note: the username is `ubuntu`, not `root` or `ec2-user`.

### Server runs out of memory

If the t3.small (2 GB RAM) isn't enough, upgrade:
```bash
# From your Mac:
aws ec2 stop-instances --instance-ids i-0abc123def456
aws ec2 modify-instance-attribute --instance-id i-0abc123def456 --instance-type t3.medium
aws ec2 start-instances --instance-ids i-0abc123def456
```

t3.medium (4 GB RAM) costs ~$30/month.
