#!/bin/bash
cd /app
git fetch origin $GIT_BRANCH 2>/dev/null
LOCAL=$(git rev-parse HEAD)
REMOTE=$(git rev-parse origin/$GIT_BRANCH)

if [ "$LOCAL" != "$REMOTE" ]; then
    echo "$(date): Update found ($LOCAL -> $REMOTE)"

    # Pull changes
    git pull origin $GIT_BRANCH

    # Install any new dependencies
    pip install -r requirements.txt --quiet 2>/dev/null

    # Run tests — rollback if they fail
    python -m pytest tests/ --tb=short -q 2>/dev/null
    if [ $? -ne 0 ]; then
        echo "$(date): Tests FAILED after update — rolling back to $LOCAL"
        git reset --hard $LOCAL
        pip install -r requirements.txt --quiet 2>/dev/null
    else
        echo "$(date): Tests passed — restarting bot"
        kill -HUP $(cat /tmp/cryptobot.pid 2>/dev/null) 2>/dev/null
    fi
else
    echo "$(date): No updates available"
fi
