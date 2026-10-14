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

# Grouping the Atlases into titles and persons (grouping-spec.md).
#
#   make group-prep COLLECTION=g RUN=<run>              # shards
#   make group-read COLLECTION=g RUN=<run> WORKERS=10   # pass 1, Claude sub-agents
#   make group-read ... ONLY=p1-title-003               # one shard, as a trial
#   make group-read ... LIMIT=4                         # the first four still pending
#   make group-validate COLLECTION=g RUN=<run> STEP=read
#   make group-consolidate COLLECTION=g RUN=<run> WORKERS=10   # pass 2, all steps
#   make group-eval                                     # GRETIL's registry against SETI
#   make group-keep COLLECTION=g RUN=<run>              # copy what the agents wrote to data/grouping/runs
#
# COLLECTION is an Atlas code: g, j, e, w or d.

only_flags = $(foreach b,$(ONLY),--only $(b))
only_words = $(if $(ONLY), Dispatch only these batches: $(ONLY).)
part_words = $(if $(LIMIT), Dispatch only the first $(LIMIT) pending batches, once, and stop there.)
group_args = --run $(RUN) --collection $(COLLECTION)

.PHONY: group-check-args group-prep group-read group-validate group-consolidate group-eval group-keep

group-check-args:
	@test -n "$(RUN)" || (echo "RUN=<run> is required" && exit 1)
	@test -n "$(COLLECTION)" || (echo "COLLECTION=<code> is required" && exit 1)

group-prep: group-check-args
	$(PYTHON) scripts/grouping_prep.py $(group_args)

group-read: group-check-args
	claude "Run the step 'read' of the grouping job for the run $(RUN) and the collection $(COLLECTION) using subagents, following agents/grouping/dispatcher.md. Use a workflow.$(workers_words)$(only_words)$(part_words) When the step is done, even with failed batches, run make group-validate RUN=$(RUN) COLLECTION=$(COLLECTION) STEP=read."

group-validate: group-check-args
	@test -n "$(STEP)" || (echo "STEP=<step> is required" && exit 1)
	$(PYTHON) scripts/grouping_validate.py $(group_args) --step $(STEP)

group-consolidate: group-check-args
	claude "Run pass 2 of the grouping job for the run $(RUN) and the collection $(COLLECTION) using subagents, following agents/grouping/dispatcher.md and its section 'Pass 2 as a whole'. Use a workflow for each fan-out step.$(workers_words) Finish every step even with failed batches."

group-eval:
	$(PYTHON) scripts/grouping_eval.py

group-keep: group-check-args
	$(PYTHON) scripts/grouping_keep.py $(group_args)
