## Description
Please include a concise summary of the change, motivation, and which issue or bug it resolves.

Fixes #(issue)

## Type of change
- [ ] Bug fix (non-breaking change which fixes an issue)
- [ ] New feature (non-breaking change which adds functionality)
- [ ] Taxonomy update (adds or improves skills/aliases)
- [ ] Documentation update
- [ ] Performance improvement / refactoring

## Checklist
- [ ] My code adheres to the style guidelines of this project
- [ ] I have performed a self-review of my own code
- [ ] I have commented my code, particularly in hard-to-understand areas
- [ ] I have added tests that prove my fix is effective or that my feature works
- [ ] If taxonomy or scoring was modified, I ran `python3 scripts/build_web_data.py` and `node scripts/parity_check.js`
- [ ] `python3 run_qc_suite.py` passes 100% with 0 errors or failures
- [ ] My commit messages follow the [Conventional Commits](https://www.conventionalcommits.org/) convention (`feat:`, `fix:`, `docs:`, `test:`)
