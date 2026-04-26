## Summary

<!-- One sentence describing what this PR changes and why. -->

## Type of change

- [ ] Bug fix
- [ ] New feature
- [ ] Documentation
- [ ] Refactor / cleanup
- [ ] Build / CI / tooling
- [ ] Release / version bump

## Test plan

- [ ] Backend tests pass (`docker compose run --rm api python -m pytest tests/ -q`)
- [ ] Frontend tests pass (`cd frontend && npm test`)
- [ ] Ruff clean (`python -m ruff check backend`)
- [ ] If touching API surface, regenerated `docs/openapi.json` + `frontend/src/generated/api.ts`
- [ ] Manual verification (describe):

## Checklist

- [ ] CHANGELOG.md updated under `[Unreleased]`
- [ ] Documentation updated (if user-facing change)
- [ ] No secrets, API keys, or credentials in committed files
- [ ] Linked issue: <!-- #N -->
