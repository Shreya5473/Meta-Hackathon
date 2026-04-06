#!/bin/bash
# Deploy to Hugging Face Spaces

set -e

echo "🚀 Starting deployment to Hugging Face Spaces..."

# Initialize git repository
echo "📍 Initializing git repository..."
git init

# Add Hugging Face Spaces remote
echo "📍 Adding Hugging Face Spaces remote..."
git remote add origin https://huggingface.co/spaces/Shreya5473/Geo-Trade

# Create .gitignore
echo "📍 Creating .gitignore..."
cat > .gitignore << 'EOF'
# Dependencies
node_modules/
.venv/
venv/
env/
ENV/

# Python
__pycache__/
*.py[cod]
*$py.class
*.so
.Python
build/
develop-eggs/
dist/
downloads/
eggs/
.eggs/
lib/
lib64/
parts/
sdist/
var/
wheels/
*.egg-info/
.installed.cfg
*.egg

# Environment
.env
.env.local
.env.*.local

# IDE
.vscode/
.idea/
*.swp
*.swo
*~
.DS_Store

# Build outputs
frontend/dist/
.next/
out/

# Logs
logs/
*.log
npm-debug.log*
yarn-debug.log*
yarn-error.log*

# Misc
.cache/
.pytest_cache/
.mypy_cache/
.coverage
htmlcov/
EOF

echo "✅ .gitignore created"

# Add all files
echo "📍 Adding all files..."
git add -A

# Commit
echo "📍 Committing changes..."
git commit -m "Deploy GeoTrade to Hugging Face Spaces"

# Push to origin main
echo "📍 Pushing to Hugging Face Spaces..."
echo ""
echo "⚠️  IMPORTANT: You will be prompted for your Hugging Face credentials."
echo "   - Use username: Shreya5473"
echo "   - Use your HF token as the password (or SSH key if configured)"
echo ""

git push -u origin main

echo ""
echo "✅ Deployment complete!"
echo "🌐 Your Space is available at: https://huggingface.co/spaces/Shreya5473/Geo-Trade"
echo "📧 Deployment notification sent to: f20240292@dubai.bits-pilani.ac.in"
