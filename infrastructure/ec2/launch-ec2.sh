#!/bin/bash
# =============================================================
# Launch a new EC2 instance for Zotta
# Run this FROM YOUR MAC to create the server on AWS.
#
# Prerequisites:
#   - AWS CLI configured (run: aws configure)
#   - An SSH key pair (the script creates one if needed)
#
# Usage: ./launch-ec2.sh
# =============================================================
set -e

INSTANCE_TYPE="t3.small"       # 2 vCPU, 2 GB RAM (~$15/mo)
AMI_REGION="us-east-1"
KEY_NAME="zotta-key"
SECURITY_GROUP_NAME="zotta-sg"

echo "========================================"
echo "  Launching Zotta EC2 Instance"
echo "========================================"

# 1. Get the latest Ubuntu 22.04 AMI
echo "[1/5] Finding latest Ubuntu AMI..."
AMI_ID=$(aws ec2 describe-images \
    --owners 099720109477 \
    --filters "Name=name,Values=ubuntu/images/hvm-ssd/ubuntu-jammy-22.04-amd64-server-*" \
              "Name=state,Values=available" \
    --query 'sort_by(Images, &CreationDate)[-1].ImageId' \
    --output text \
    --region $AMI_REGION)
echo "  AMI: $AMI_ID"

# 2. Create SSH key pair (if it doesn't exist)
echo "[2/5] Setting up SSH key..."
if ! aws ec2 describe-key-pairs --key-names $KEY_NAME --region $AMI_REGION >/dev/null 2>&1; then
    aws ec2 create-key-pair \
        --key-name $KEY_NAME \
        --query 'KeyMaterial' \
        --output text \
        --region $AMI_REGION > ~/.ssh/${KEY_NAME}.pem
    chmod 400 ~/.ssh/${KEY_NAME}.pem
    echo "  Created new key pair: ~/.ssh/${KEY_NAME}.pem"
else
    echo "  Key pair '$KEY_NAME' already exists."
fi

# 3. Create security group (if it doesn't exist)
echo "[3/5] Setting up security group..."
VPC_ID=$(aws ec2 describe-vpcs --filters "Name=isDefault,Values=true" --query 'Vpcs[0].VpcId' --output text --region $AMI_REGION)

SG_ID=$(aws ec2 describe-security-groups \
    --filters "Name=group-name,Values=$SECURITY_GROUP_NAME" "Name=vpc-id,Values=$VPC_ID" \
    --query 'SecurityGroups[0].GroupId' \
    --output text \
    --region $AMI_REGION 2>/dev/null)

if [ "$SG_ID" = "None" ] || [ -z "$SG_ID" ]; then
    SG_ID=$(aws ec2 create-security-group \
        --group-name $SECURITY_GROUP_NAME \
        --description "Zotta lending application" \
        --vpc-id $VPC_ID \
        --query 'GroupId' \
        --output text \
        --region $AMI_REGION)

    # Allow SSH (port 22)
    aws ec2 authorize-security-group-ingress \
        --group-id $SG_ID \
        --protocol tcp --port 22 --cidr 0.0.0.0/0 \
        --region $AMI_REGION

    # Allow HTTP (port 80)
    aws ec2 authorize-security-group-ingress \
        --group-id $SG_ID \
        --protocol tcp --port 80 --cidr 0.0.0.0/0 \
        --region $AMI_REGION

    # Allow HTTPS (port 443)
    aws ec2 authorize-security-group-ingress \
        --group-id $SG_ID \
        --protocol tcp --port 443 --cidr 0.0.0.0/0 \
        --region $AMI_REGION

    echo "  Created security group: $SG_ID (ports 22, 80, 443 open)"
else
    echo "  Security group already exists: $SG_ID"
fi

# 4. Launch EC2 instance
echo "[4/5] Launching EC2 instance ($INSTANCE_TYPE)..."
INSTANCE_ID=$(aws ec2 run-instances \
    --image-id $AMI_ID \
    --instance-type $INSTANCE_TYPE \
    --key-name $KEY_NAME \
    --security-group-ids $SG_ID \
    --block-device-mappings '[{"DeviceName":"/dev/sda1","Ebs":{"VolumeSize":20,"VolumeType":"gp3"}}]' \
    --tag-specifications "ResourceType=instance,Tags=[{Key=Name,Value=Zotta}]" \
    --query 'Instances[0].InstanceId' \
    --output text \
    --region $AMI_REGION)
echo "  Instance ID: $INSTANCE_ID"

# 5. Wait for it to be running and get public IP
echo "[5/5] Waiting for instance to start..."
aws ec2 wait instance-running --instance-ids $INSTANCE_ID --region $AMI_REGION

PUBLIC_IP=$(aws ec2 describe-instances \
    --instance-ids $INSTANCE_ID \
    --query 'Reservations[0].Instances[0].PublicIpAddress' \
    --output text \
    --region $AMI_REGION)

echo ""
echo "========================================"
echo "  EC2 Instance Ready!"
echo "========================================"
echo ""
echo "  Instance ID:  $INSTANCE_ID"
echo "  Public IP:    $PUBLIC_IP"
echo "  SSH Key:      ~/.ssh/${KEY_NAME}.pem"
echo ""
echo "  NEXT STEPS:"
echo ""
echo "  1. Wait 30 seconds for the server to fully boot, then SSH in:"
echo ""
echo "     ssh -i ~/.ssh/${KEY_NAME}.pem ubuntu@${PUBLIC_IP}"
echo ""
echo "  2. Once connected, run the setup script:"
echo ""
echo "     curl -sSL https://raw.githubusercontent.com/energet52/Zotta/main/infrastructure/ec2/server-setup.sh | bash"
echo ""
echo "  3. After setup completes (~3-5 minutes), open in your browser:"
echo ""
echo "     http://${PUBLIC_IP}"
echo ""
echo "  To STOP the instance (stop paying):"
echo "     aws ec2 stop-instances --instance-ids $INSTANCE_ID"
echo ""
echo "  To START it again:"
echo "     aws ec2 start-instances --instance-ids $INSTANCE_ID"
echo ""
echo "  To TERMINATE (delete permanently):"
echo "     aws ec2 terminate-instances --instance-ids $INSTANCE_ID"
echo ""
