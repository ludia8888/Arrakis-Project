#!/bin/bash
# Emergency Commit Script for Arrakis Platform
# Use this script when pre-commit hooks are blocking critical fixes
# CAUTION: This bypasses all quality checks - use only in emergencies!

set -e

# Colors for output
RED='\033[0;31m'
YELLOW='\033[1;33m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Emergency commit flag file
EMERGENCY_FLAG=".emergency_commit_in_progress"

# Function to print colored output
print_color() {
    color=$1
    message=$2
    echo -e "${color}${message}${NC}"
}

# Function to log emergency commit
log_emergency_commit() {
    local commit_msg="$1"
    local reason="$2"
    local timestamp=$(date '+%Y-%m-%d %H:%M:%S')
    local user=$(git config user.name || echo "unknown")

    # Create emergency log directory if it doesn't exist
    mkdir -p .emergency_commits

    # Log the emergency commit
    cat >> .emergency_commits/emergency_log.json << EOF
{
  "timestamp": "$timestamp",
  "user": "$user",
  "commit_message": "$commit_msg",
  "reason": "$reason",
  "branch": "$(git branch --show-current)",
  "files_changed": $(git diff --cached --name-only | wc -l)
}
EOF
}

# Function to show warning and get confirmation
show_warning() {
    print_color "$RED" "╔════════════════════════════════════════════════════════════╗"
    print_color "$RED" "║                    ⚠️  EMERGENCY COMMIT ⚠️                   ║"
    print_color "$RED" "╚════════════════════════════════════════════════════════════╝"
    echo
    print_color "$YELLOW" "This script will bypass ALL pre-commit hooks including:"
    echo "  • Python syntax validation"
    echo "  • Code formatting (black, isort)"
    echo "  • Type checking (mypy)"
    echo "  • Security checks"
    echo "  • Indentation validation"
    echo
    print_color "$RED" "⚠️  USE ONLY FOR CRITICAL PRODUCTION FIXES! ⚠️"
    echo
}

# Function to create follow-up todo
create_followup_todo() {
    local commit_hash="$1"
    local timestamp=$(date '+%Y-%m-%d %H:%M:%S')

    cat >> .emergency_commits/followup_todos.md << EOF

## Emergency Commit Follow-up Required
- **Date**: $timestamp
- **Commit**: $commit_hash
- **Branch**: $(git branch --show-current)

### Required Actions:
1. [ ] Run full test suite: \`pytest tests/\`
2. [ ] Run pre-commit hooks manually: \`pre-commit run --all-files\`
3. [ ] Fix any issues found
4. [ ] Create follow-up PR with fixes

---
EOF
}

# Main script
main() {
    # Check if we're in a git repository
    if ! git rev-parse --git-dir > /dev/null 2>&1; then
        print_color "$RED" "Error: Not in a git repository!"
        exit 1
    fi

    # Show warning
    show_warning

    # Get confirmation
    read -p "Do you want to proceed with emergency commit? (type 'EMERGENCY' to confirm): " confirmation
    if [ "$confirmation" != "EMERGENCY" ]; then
        print_color "$YELLOW" "Emergency commit cancelled."
        exit 0
    fi

    # Get commit message
    echo
    read -p "Enter commit message: " commit_msg
    if [ -z "$commit_msg" ]; then
        print_color "$RED" "Error: Commit message cannot be empty!"
        exit 1
    fi

    # Get reason for emergency commit
    echo
    print_color "$YELLOW" "Why is this an emergency commit?"
    echo "1. Critical production bug fix"
    echo "2. Security vulnerability patch"
    echo "3. Data corruption prevention"
    echo "4. Service outage resolution"
    echo "5. Other (specify)"
    read -p "Select reason (1-5): " reason_num

    case $reason_num in
        1) reason="Critical production bug fix";;
        2) reason="Security vulnerability patch";;
        3) reason="Data corruption prevention";;
        4) reason="Service outage resolution";;
        5)
            read -p "Specify reason: " custom_reason
            reason="Other: $custom_reason"
            ;;
        *)
            print_color "$RED" "Invalid selection!"
            exit 1
            ;;
    esac

    # Create emergency flag
    touch "$EMERGENCY_FLAG"

    # Log the emergency commit
    log_emergency_commit "$commit_msg" "$reason"

    # Show files to be committed
    echo
    print_color "$BLUE" "Files to be committed:"
    git diff --cached --name-status

    # Perform the commit with --no-verify
    echo
    print_color "$YELLOW" "Performing emergency commit..."

    # Add emergency tag to commit message
    full_commit_msg="🚨 EMERGENCY: $commit_msg

Reason: $reason
Pre-commit hooks bypassed - follow-up required
Emergency commit by: $(git config user.name || echo 'unknown')"

    if git commit --no-verify -m "$full_commit_msg"; then
        commit_hash=$(git rev-parse HEAD)
        print_color "$GREEN" "✅ Emergency commit successful: $commit_hash"

        # Create follow-up todo
        create_followup_todo "$commit_hash"

        # Show follow-up instructions
        echo
        print_color "$YELLOW" "╔════════════════════════════════════════════════════════════╗"
        print_color "$YELLOW" "║                  FOLLOW-UP REQUIRED                        ║"
        print_color "$YELLOW" "╚════════════════════════════════════════════════════════════╝"
        echo
        echo "1. Run pre-commit hooks manually:"
        echo "   $ pre-commit run --all-files"
        echo
        echo "2. Fix any issues found"
        echo
        echo "3. Create a follow-up commit with fixes"
        echo
        echo "4. Review the emergency commit log:"
        echo "   $ cat .emergency_commits/emergency_log.json"
        echo
        print_color "$RED" "⚠️  DO NOT PUSH without running quality checks! ⚠️"

        # Ask if user wants to push
        echo
        read -p "Do you want to push this emergency commit? (yes/no): " push_confirm
        if [ "$push_confirm" = "yes" ]; then
            print_color "$YELLOW" "Pushing emergency commit..."
            if git push; then
                print_color "$GREEN" "✅ Emergency commit pushed successfully"
                print_color "$RED" "⚠️  Remember to create a follow-up PR with fixes!"
            else
                print_color "$RED" "❌ Push failed. Please push manually when ready."
            fi
        else
            print_color "$YELLOW" "Commit created locally. Push when ready with: git push"
        fi
    else
        print_color "$RED" "❌ Emergency commit failed!"
        rm -f "$EMERGENCY_FLAG"
        exit 1
    fi

    # Clean up
    rm -f "$EMERGENCY_FLAG"
}

# Run main function
main "$@"
