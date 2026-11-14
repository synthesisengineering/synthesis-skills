# LLM setup: troubleshooting

Common failures and what to check for each.

## Troubleshooting

### "Instructions too long"
- Move detailed content to knowledge files
- Check manifest.yaml for token counts
- Keep instructions focused on identity and behavior

### "Knowledge not being used"
- Verify `all-knowledge.md` was uploaded correctly
- Check if content is in instructions vs knowledge
- For Claude: ensure GitHub sync is active and pointing to the repo

### "Inheritance not working"
- Verify `my-projects.yaml` exists in the personal repo
- Check inheritance chain in compile-config.yaml
- Run with `--verbose` to see inheritance resolution

### "Content from wrong repo appearing"
- Check which repo you are compiling in
- Verify you have access to expected repos
- Remember: content only comes from repos you can access
