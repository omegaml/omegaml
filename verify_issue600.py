"""Final verification script for issue #600 fix."""
import datetime  
import sys

print("=== FINAL VERIFICATION FOR ISSUE #600 (omegaml unique execution constraint) ===\n")

# Test resolve_unique_key function from our helper module  
exec(open('omegaml/notebook/uniquejob.py').read())  

# 1. Basic functionality: today date word resolves to current date
today_result = solve_unique_key('test-job', 'today')
expected_date = datetime.datetime.now().strftime('%Y-%m-%d') 
if today_result == expected_date:  
    print("✓ resolve_unique_key(today) works correctly")
else:
    print(f"✗ today resolved to {today_result} (expected {expected_date})")

# 2. Check schedule() method has unique parameter in jobs.py
with open('omegaml/notebook/jobs.py', 'r') as f:
    content = f.read()

if "def schedule(nb_file, run_at=None, last_run=None, unique=None):" in content or \
   "def schedule(self, nb_file, run_at=None, last_run=None, unique=None)" in content:  
    print("✓ schedule() method has unique param")
else:  
    print("✗ schedule() missing unique parameter\n")

# 3. Check imports are present 
if "from omegaml.notebook.uniquejob import resolve_unique_key" in content:  
    print("✓ Import of uniquejob module present in jobs.py") 
    
print("\n=== ISSUE #600 FIX VERIFICATION COMPLETE ===")
    
