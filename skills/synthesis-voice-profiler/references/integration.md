# Voice profiler: integration

Which skills consume the voice profile once the user adds it to their agent instruction file.

## Integration

After the user adds the voice profile to their agent instruction file:

- **synthesis-article-writing** will apply it during Phase 2 (Writing)
- **synthesis-blog-refresh** will use it for voice consistency checks
- **synthesis-concise-messaging** will apply voice preferences to condensed messages
- **synthesis-content-distribution** will adapt posts to match voice across platforms
- **synthesis-content-quality** will flag deviations from the negative constraints during quality review
- Any custom skills that say to apply voice preferences from agent instructions will consume it automatically

No additional wiring is needed. Agent instruction files are the integration layer.
