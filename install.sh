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
if ! grep -q "course-open" ~/.zshrc; then
    echo "✍️ Adding aliases to ~/.zshrc..."
    echo "" >> ~/.zshrc
    echo "# === TELO ENGINE ALIASES ===" >> ~/.zshrc
    echo "alias add='python3 ~/.course/main.py add'" >> ~/.zshrc
    echo "alias list='python3 ~/.course/main.py list'" >> ~/.zshrc
    echo "alias play='python3 ~/.course/main.py open'" >> ~/.zshrc
    echo "alias telo-login='python3 ~/.course/main.py login'" >> ~/.zshrc
    echo "course-stop() { pkill -f \"python3.*.course/main.py\"; echo \"🛑 All servers stopped.\"; }" >> ~/.zshrc
    
    echo "✅ Aliases added successfully!"
    echo "🔄 Run 'source ~/.zshrc' to start using commands."
else
    echo "ℹ️ Aliases already exist in ~/.zshrc"
fi

echo "🎉 Setup Complete! Ab aap 'course-add' ya 'login-telo' use kar sakte hain."