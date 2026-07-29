#!/usr/bin/env bash
# Board sync for Project 12. Sole writer of board Status values in the /task pipeline.
# Fired by a PostToolUse hook on Write|Edit; acts only when the edited file is
# .claude/board-state.json. Reads {"issue": N, "stage": "..."} from that file,
# sets the card's Status, then recomputes the parent story's Status as the
# minimum stage across its sub-issues. It can ONLY set Status field values —
# it never creates, closes, or deletes anything.
set -euo pipefail

OWNER="paulomtts"
REPO="pyjinhx"
PROJECT_ID="PVT_kwHOBZmM8c4BewiO"
STATUS_FIELD_ID="PVTSSF_lAHOBZmM8c4BewiOzhZIXw8"

# Stage allowlist, pipeline order. Rank drives the story's min-stage computation.
STAGES=(backlog spec ready implementing in-review testing done)
OPTION_IDS=(a4448373 07356194 5d5646cc 20e71636 6554ad50 f397e470 ce6ea6d1)
OPTION_NAMES=("Backlog" "Spec" "Ready" "In progress" "In review" "Testing" "Done")

# Only react to writes of the state file; every other Write/Edit exits silently.
INPUT=$(cat)
FILE_PATH=$(jq -r '.tool_input.file_path // empty' <<<"$INPUT")
[[ "$FILE_PATH" == */.claude/board-state.json ]] || exit 0

STATE_FILE="$FILE_PATH"
ISSUE=$(jq -r '.issue // empty' "$STATE_FILE")
STAGE=$(jq -r '.stage // empty' "$STATE_FILE")

[[ "$ISSUE" =~ ^[0-9]+$ ]] || { echo "board-sync: bad issue '$ISSUE'" >&2; exit 2; }
RANK=-1
for i in "${!STAGES[@]}"; do [[ "${STAGES[$i]}" == "$STAGE" ]] && RANK=$i; done
[[ $RANK -ge 0 ]] || { echo "board-sync: bad stage '$STAGE' (allowed: ${STAGES[*]})" >&2; exit 2; }

item_id_for_issue() { # issue number -> project item id on Project 12
  gh api graphql -f query='query($n:Int!){repository(owner:"'"$OWNER"'",name:"'"$REPO"'"){issue(number:$n){projectItems(first:10){nodes{id project{id}}}}}}' \
    -F n="$1" --jq '.data.repository.issue.projectItems.nodes[] | select(.project.id=="'"$PROJECT_ID"'") | .id'
}

set_status() { # item id, option id
  gh api graphql -f query='mutation($i:ID!,$o:String!){updateProjectV2ItemFieldValue(input:{projectId:"'"$PROJECT_ID"'",itemId:$i,fieldId:"'"$STATUS_FIELD_ID"'",value:{singleSelectOptionId:$o}}){projectV2Item{id}}}' \
    -f i="$1" -f o="$2" --jq '.data.updateProjectV2ItemFieldValue.projectV2Item.id' >/dev/null
}

ITEM_ID=$(item_id_for_issue "$ISSUE")
[[ -n "$ITEM_ID" ]] || { echo "board-sync: issue #$ISSUE not on project" >&2; exit 2; }
set_status "$ITEM_ID" "${OPTION_IDS[$RANK]}"
echo "board-sync: #$ISSUE -> ${OPTION_NAMES[$RANK]}"

# Parent story mirrors the least-advanced of its sub-issues.
PARENT_JSON=$(gh api graphql -f query='query($n:Int!){repository(owner:"'"$OWNER"'",name:"'"$REPO"'"){issue(number:$n){parent{number subIssues(first:50){nodes{projectItems(first:10){nodes{project{id} fieldValueByName(name:"Status"){... on ProjectV2ItemFieldSingleSelectValue{name}}}}}}}}}}' -F n="$ISSUE")
PARENT_NUM=$(jq -r '.data.repository.issue.parent.number // empty' <<<"$PARENT_JSON")
[[ -n "$PARENT_NUM" ]] || exit 0

MIN_RANK=$((${#STAGES[@]} - 1))
while read -r name; do
  for i in "${!OPTION_NAMES[@]}"; do
    [[ "${OPTION_NAMES[$i]}" == "$name" && $i -lt $MIN_RANK ]] && MIN_RANK=$i
  done
done < <(jq -r '.data.repository.issue.parent.subIssues.nodes[].projectItems.nodes[] | select(.project.id=="'"$PROJECT_ID"'") | .fieldValueByName.name // "Backlog"' <<<"$PARENT_JSON")

PARENT_ITEM=$(item_id_for_issue "$PARENT_NUM")
[[ -n "$PARENT_ITEM" ]] || exit 0
set_status "$PARENT_ITEM" "${OPTION_IDS[$MIN_RANK]}"
echo "board-sync: story #$PARENT_NUM -> ${OPTION_NAMES[$MIN_RANK]} (min of sub-issues)"
