# Inspectable review material

Put the actual material in `review_assets` when a decision concerns a draft,
file, image or recording. Keep context and the recommendation in their existing
fields. The reader should see the complete material before deciding.

The existing generator, summary and recorder own this contract. No new service,
renderer package or action authority is introduced. Every material field belongs
to the canonical spec digest: revision, delivery format, destinations,
attachments, titles, descriptions, content and byte digests. Any change starts a
new persistence generation and invalidates the old returned summary.

## Row contract

A row with `review_assets` must also have:

- `revision`: a nonempty identifier, at most 256 UTF-8 bytes.
- `delivery`: exactly `format`, `destinations` and `attachments`. Format is a
  nonempty string of at most 256 bytes. Destinations is a list of at most 64
  explicit target strings, each at most 2,048 bytes; an empty list means none is
  declared. Attachments lists unique IDs of assets included in this row.
- `review_assets`: one through 16 typed asset objects. Each has a unique `id`
  (ASCII letters, numbers, underscores or hyphens, starting with a letter or
  number, at most 64 characters), a nonempty `title` of at most 512 bytes,
  `kind`, and `content`. An optional `description` is at most 4,096 bytes.

Use the destination strings to state the exact role and target, such as
`To: reader@example.test`; they are descriptive data, never a send instruction.
Include any subject or header material in the complete correspondence text.
Changing those bytes changes the binding. The action owner must still verify
its authentic approval, actual recipient fields, current payload and permissions.

```json
{
  "id": "draft-decision",
  "label": "Review the synthetic message",
  "revision": "draft-3",
  "delivery": {
    "format": "Plain text email",
    "destinations": ["To: reader@example.test"],
    "attachments": []
  },
  "review_assets": [{
    "id": "draft",
    "title": "Complete synthetic message",
    "kind": "correspondence",
    "content": {
      "text": "Hello, fixture.\n\nThis is the complete synthetic message.",
      "sha256": "REPLACE_WITH_SHA256_OF_EXACT_UTF8_TEXT"
    }
  }]
}
```

This fragment illustrates the material fields; add the normal recommendation,
options, context and impact before building a packet. The example digest is
intentionally not valid. Compute it from the exact text instead of copying it.

## Text and Markdown

For `correspondence`, `plain_text`, `markdown` and `code`, `content` contains
exactly `text` and lowercase `sha256`. The generator checks SHA-256 against the
actual UTF-8 bytes. Text must be nonempty and at most 1 MiB; control characters
other than tab, CR and LF are refused. Unicode and original line endings remain
bound. No filename is accepted for text assets; downloads use `<id>.txt`.

Correspondence and plain text preserve paragraphs and line breaks. Code uses a
monospaced view. Markdown supports paragraphs, ATX headings, unordered lists and
triple-backtick code blocks. Soft line breaks within a paragraph render as
spaces. Headings use one visual level inside the asset's accessible section.
Inline markup, links, images, tables and raw HTML are displayed as text. They do
not run, fetch resources or become clickable markup. Exact source text remains
available beside the rendered view.

Copy selects the source first, then tries the browser's copy mechanisms. Denied,
throwing or unresolved clipboard requests receive a manual-copy message within
two seconds. A reported success means the browser reported success; it is not
independent clipboard readback. Where a textarea normalizes CR/CRLF, automatic
copy receives the original string and the manual fallback names the limitation.
Download preserves the exact UTF-8 bytes regardless of clipboard conventions.

## Binary assets

For binary content, require exactly `base64`, `sha256`, `size` and `media_type`.
The generator decodes strict canonical base64 and checks the actual size,
digest, allowed type and file signature. Each asset is at most 4 MiB. Binary
assets need an accessible `description` and a plain `filename` matching the
allowed extension. Raster dimensions must be readable within a bounded header,
at most 8,192 per side and 16 megapixels in total (16,777,216 pixels). JPEG
dimension discovery reads at most 128 KiB. Paths, executable types, HTML and SVG
are refused.

| Kind | Allowed types | Reader behavior |
|---|---|---|
| `image` | PNG, JPEG, GIF, WebP | Embedded image, description and exact download |
| `audio` | MP3, WAV, Ogg | Native controls, no autoplay or preload; exact download |
| `video` | MP4, WebM | Native controls, no autoplay or preload; exact download |
| `document` | PDF | Explicit preview-unavailable notice and exact PDF download |

The packet never embeds a PDF viewer or runs document code. Open the downloaded
PDF in an appropriate reader before deciding. Format signatures and digest
checks establish byte custody; they do not establish that every browser has the
codec, that a document is harmless, or that the reader inspected it. Media
rendering failures are visible and retain the bound download. Exact text and
images can also open through a local Blob URL. Blob URLs do not confer external
publication or network authority.

All decoded review material together is limited to 4 MiB. Spec files are
limited to 8 MiB, whether read from a file or from standard input; the generator
reads the spec once and builds from those bytes. The final generated HTML also
has an 8 MiB ceiling, matching the existing context-doctor reader. JSON escaping
and page markup count toward that ceiling, so an otherwise valid large spec may
be refused before filing. Use fewer assets or explicit unresolved references
when the complete page exceeds it; do not widen the shared protection.

The packet embeds the bytes, so
later changes to an original local file or website cannot replace its material.
The new revision must be deliberately rebuilt from new exact bytes.

## Unavailable material

Use `content: {"unavailable": "Exact reason"}` when the bytes are unavailable.
An optional `source` must be an HTTPS URL without credentials or a nonstandard
port. It is an explicit external link, never a fetch or verified asset. Local
paths, `file:` links, relative URLs, script URLs and extra content keys are
refused. Keep an inaccessible local locator in context if it helps explain the
missing source; the generator does not open it.

The row stays readable and accepts notes, but choices and bulk selection are
disabled. The recorder also refuses a selected ruling for that row, including a
forged summary with the right spec digest. Rebuild from the verified content
before using packet selections for that material.

## Authority and operational boundaries

Recorded rulings retain the full assets, revision and delivery envelope. They
continue to declare `authorization.granted: false` and unverified identity.
Neither a locally generated page nor a perfect pasted summary authenticates a
principal. Existing authentic grants remain valid within their original scope;
this format does not require reapproval of an already authorized action.

The generation, recording and browser fixtures (`tests/test_packet_*.py`)
use only synthetic material. Their passing results prove transport and reader
behavior, not a real recipient, principal approval, publication or native agent
acceptance. Before handing over a real packet, inspect its complete content at
both desktop and narrow widths and verify the filed generation with the existing
context-doctor owner. Never substitute a screenshot for the underlying bytes.
