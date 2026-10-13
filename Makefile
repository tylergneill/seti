# SETI: matching the master against the Pandit Project.
#
#   make match                      # mechanical matcher, open slots only
#   make match SCOPE=all            # mechanical matcher, every row
#   make research-prep LIMIT=50     # cut rows into batches for the LLM pass
#   make research RUN=<run>         # Claude sub-agents research the batches
#   make research-apply RUN=<run>   # write their findings into the master
#
# Both matchers edit data/seti-master.csv in place and write what they were
# less sure of to reports/. Review the master as a diff.
#
# SCOPE=open (default) touches only '...' slots. SCOPE=all re-identifies
# every row and may replace IDs already there. THRESHOLD (default 0.9) is
# the confidence at which a finding is written rather than noted.

PYTHON ?= python3
SCOPE ?= open
THRESHOLD ?= 0.9
BATCH ?= 10

collection_flag = $(if $(COLLECTION),--collection "$(COLLECTION)")
limit_flag = $(if $(LIMIT),--limit $(LIMIT))
run_flag = $(if $(RUN),--run $(RUN))
dry_flag = $(if $(DRY),--dry-run)
workers_words = $(if $(WORKERS), Keep up to $(WORKERS) sub-agents in flight at a time.)

.PHONY: match research-prep research research-apply

match:
	$(PYTHON) scripts/match.py --scope $(SCOPE) --threshold $(THRESHOLD) $(collection_flag) $(dry_flag)

research-prep:
	$(PYTHON) scripts/research_prep.py --scope $(SCOPE) --batch-size $(BATCH) $(collection_flag) $(limit_flag) $(run_flag)

research:
	@test -n "$(RUN)" || (echo "RUN=<run> is required; research-prep prints the name" && exit 1)
	claude "Research the pending batches using subagents, following agents/dispatcher.md, for the run $(RUN). Use a workflow.$(workers_words) When the run is done, even with failed batches, run make research-apply RUN=$(RUN)."

research-apply:
	@test -n "$(RUN)" || (echo "RUN=<run> is required" && exit 1)
	$(PYTHON) scripts/research_apply.py --run $(RUN) --threshold $(THRESHOLD) $(dry_flag)
