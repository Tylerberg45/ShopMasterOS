#!/bin/bash
# Keep-alive script for GitHub Codespaces
# This prevents idle timeout by simulating activity

echo "🔄 Starting Codespace keep-alive..."
echo "⚡ This will prevent idle timeout"
echo "🛑 Press Ctrl+C to stop"

# Function to simulate activity
keep_alive() {
    while true; do
        # Touch a timestamp file to show activity
        echo "$(date): Keep-alive ping" >> /tmp/keepalive.log
        
        # Ping localhost to keep network active
        curl -s http://localhost:8000/health > /dev/null 2>&1 || true
        
        # Wait 5 minutes before next ping
        sleep 300
    done
}

# Run keep-alive in background
keep_alive &
KEEPALIVE_PID=$!

# Wait for user to stop
trap "kill $KEEPALIVE_PID 2>/dev/null; echo '✅ Keep-alive stopped'; exit" SIGINT SIGTERM

echo "✅ Keep-alive running (PID: $KEEPALIVE_PID)"
echo "📊 Monitor activity: tail -f /tmp/keepalive.log"
wait
