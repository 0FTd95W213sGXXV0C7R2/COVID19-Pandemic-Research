"""Run the independent cancer audit and its historical evidence checks."""
from audit_cancer_integration import main as core
from cancer_audit_supplement import main as supplement

if __name__ == '__main__':
    core()
    supplement()
