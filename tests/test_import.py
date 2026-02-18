import traceback
import sys

sys.path.insert(0, '.')

try:
    from agents.base.enhanced_agent_factory import EnhancedAgentFactory
    print("SUCCESS: EnhancedAgentFactory imported successfully")
except Exception as e:
    print(f"ERROR: {e}")
    print("\nFull traceback:")
    traceback.print_exc()
