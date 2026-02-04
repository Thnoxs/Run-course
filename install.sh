#!/bin/bash

echo "🚀 Telo Engine Setup Start ho raha hai..."

# 1. .course folder ko Home Directory (~) me move karna
if [ -d ".course" ]; then
    cp -r .course ~/
    echo "✅ Engine files moved to ~/.course"
else
    mkdir ~/.course
    cp main.py requirements.txt icon.png logo.png ~/.course/
    echo "✅ Individual files moved to ~/.course"
fi

# 2. Python Dependencies install karna
echo "📦 Dependencies install ho rahi hain..."
pip3 install -r requirements.txt

# 3. Zsh Shortcuts (Aliases) add karna automatically
# Check if alias already exists to avoid duplication
if ! grep -q "telo()" ~/.zshrc; then
    echo "✍️ Adding 'telo' function to ~/.zshrc..."
    echo "" >> ~/.zshrc
    echo "# === TELO ENGINE ALIASES ===" >> ~/.zshrc
    echo 'telo() {
    case $1 in
        add)
            python3 ~/.course/main.py add "${@:2}"
            ;;
        list)
            python3 ~/.course/main.py list "${@:2}"
            ;;
        play)
            python3 ~/.course/main.py open "${@:2}"
            ;;
        login)
            python3 ~/.course/main.py login "${@:2}"
            ;;
        *)
            echo "Usage: telo {add|list|play|login}"
            echo "Example: telo play '\''React Tutorial'\''"
            ;;
    esac
}' >> ~/.zshrc

    echo "✅ Telo function added successfully!"
    echo "🔄 Run 'source ~/.zshrc' to start using commands."
else
    echo "ℹ️ Telo function already exists in ~/.zshrc"
fi

echo "🎉 Setup Complete! Ab aap 'course-add' ya 'login-telo' use kar sakte hain."