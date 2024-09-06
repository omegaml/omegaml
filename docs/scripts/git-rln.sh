#!/bin/bash
# prompt (chatgpt):
#   git command line utility to produce release notes from commit history.
#   write a bash function to accept baseline and target commit ref. output MD
#   format text output in the same style as github automatic release notes.
generate_release_notes() {
    local baseline_ref="$1"
    local target_ref="$2"

    # Fetch commit log between the baseline and target ref
    local commits=$(git log --pretty=format:"%H %s" "$baseline_ref".."$target_ref")

    if [[ -z "$commits" ]]; then
        echo "No commits found between $baseline_ref and $target_ref."
        return
    fi

    # Group commits by type (based on conventional commits)
    declare -A commit_groups
    commit_groups["Features"]=""
    commit_groups["Bug Fixes"]=""
    commit_groups["Documentation"]=""
    commit_groups["Refactor"]=""
    commit_groups["Performance"]=""
    commit_groups["Tests"]=""
    commit_groups["Chores"]=""
    commit_groups["Changes"]=""

    while IFS= read -r line; do
        commit_hash=$(echo "$line" | awk '{print $1}' | cut -c1-7)
        commit_message=$(echo "$line" | cut -d' ' -f2-)
        commit_url=$(generate_commit_url $commit_hash)

        # Determine the type of commit based on its message
        case "$commit_message" in
            feat*) commit_groups["Features"]+="\n- ${commit_message} [$commit_hash][$commit_hash](${commit_url})" ;;
            fix*) commit_groups["Bug Fixes"]+="\n- ${commit_message} [$commit_hash](${commit_url})" ;;
            docs*) commit_groups["Documentation"]+="\n- ${commit_message} [$commit_hash](${commit_url})" ;;
            refactor*) commit_groups["Refactor"]+="\n- ${commit_message} [$commit_hash](${commit_url})" ;;
            perf*) commit_groups["Performance"]+="\n- ${commit_message} [$commit_hash](${commit_url})" ;;
            test*) commit_groups["Tests"]+="\n- ${commit_message} [$commit_hash](${commit_url})" ;;
            chore*) commit_groups["Chores"]+="\n- ${commit_message} [$commit_hash](${commit_url})" ;;
            *) commit_groups["Changes"]+="\n- ${commit_message} [$commit_hash](${commit_url})" ;;
        esac
    done <<< "$commits"

    # Output the release notes in Markdown format
    echo " "

    for group in "${!commit_groups[@]}"; do
        if [[ -n "${commit_groups[$group]}" ]]; then
            echo -e "\n### $group\n${commit_groups[$group]}"
        fi
    done
}


generate_commit_url() {
    local commit_hash="$1"

    # Get the remote URL (assumes the remote is named 'origin')
    local remote_url=$(git config --get remote.origin.url)

    if [[ -z "$remote_url" ]]; then
        echo "No remote repository found."
        return
    fi

    # Process the remote URL to match the GitHub format
    local repo_url
    if [[ "$remote_url" =~ ^git@github.com:(.*)\.git$ ]]; then
        repo_url="https://github.com/${BASH_REMATCH[1]}"
    elif [[ "$remote_url" =~ ^https://github.com/(.*)\.git$ ]]; then
        repo_url="https://github.com/${BASH_REMATCH[1]}"
    else
        echo "Unsupported remote URL format: $remote_url"
        return
    fi

    # Generate the commit URL
    local commit_url="${repo_url}/commit/${commit_hash}"

    echo "$commit_url"
}

# Usage: generate_commit_url <commit_hash>
# Example: generate_commit_url d6fde92930d4715a2b49857d24b940956b26d2d3


# Usage: generate_release_notes <baseline_ref> <target_ref>
# Example: generate_release_notes v1.0.0 HEAD

generate_release_notes $1 $2