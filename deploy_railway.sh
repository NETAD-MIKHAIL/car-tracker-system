#!/bin/bash
# Railway Deployment Script

echo "🚀 Deploying Car Tracker to Railway..."

# Check if Railway CLI is installed
if ! command -v railway &> /dev/null; then
    echo "Installing Railway CLI..."
    curl -fsSL https://railway.app/install.sh | sh
fi

# Login to Railway
echo "Please login to Railway:"
railway login

# Create new project
echo "Creating Railway project..."
railway init car-tracker-system

# Set environment variables
echo "Setting environment variables..."
echo "Enter your BOT_TOKEN:"
read -s BOT_TOKEN
railway variables set BOT_TOKEN=$BOT_TOKEN

echo "Enter your CHAT_ID:"
read CHAT_ID
railway variables set CHAT_ID=$CHAT_ID

echo "Enter your CARTRACK_USERNAME:"
read CARTRACK_USERNAME
railway variables set CARTRACK_USERNAME=$CARTRACK_USERNAME

echo "Enter your CARTRACK_PASSWORD:"
read -s CARTRACK_PASSWORD
railway variables set CARTRACK_PASSWORD=$CARTRACK_PASSWORD

# Deploy
echo "Deploying..."
railway up

echo "✅ Deployment complete!"
echo "Your app will be available at the URL shown above."