## Rules, Development, and Workflow
## 1. Make a plan
 - ensure that you create a plan everytime before continuing with the prompt
 - create a test for the result of the prompt
 - Make sure that the result passes the test with at least 90 percent accuracy
 - Follow the plan from the beginning, and use a loop cycle when stuck, don't stay stuck
## 2. Progress
 - Make sure that you log your progress each time after finishing a prompt, for the first time, create progress.md
 - Create plan.md for your next steps, I'm clearing the context everytime so ensure that you have a plan beforehand
 - Create a github repo and push to git everytime
## 2. Engineering Principles
Document-as-Protocol: Write specs, training summaries, and benchmark findings to docs/*.md rather than long chat dumps.
Critic Separation: Before enabling live SendInput mouse output, a Critic check must verify the Studio foreground lock, kill-switch binding, and <10ms frame latency.
Context Isolation: Keep audio_pan.py, capture_dataset.py, vision_tracker.py, and pid_controller.py strictly decoupled.
Deterministic Artifacts: All datasets, model weights (models/zombie_best.pt), and CSV logs are saved deterministically inside D:\StudioVisibilityBench.