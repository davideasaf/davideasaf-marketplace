---
name: codex-image-gen
description: >
  Generate images via OpenAI's Codex CLI using gpt-image-2 (ImageGen v2). Use this skill
  whenever the user wants to generate, edit, or compose images via Codex — text-to-image,
  image-to-image edits, or multi-reference composition (e.g. "put this logo onto that
  mockup"). Triggers include "/codex-image-gen", "generate an image with codex", "use
  codex to make a picture", "have codex edit this image", or any image-creation request
  where the user mentions Codex or OpenAI's image model. Saves to `~/Downloads/` by default.
---

# Codex Image Gen

Wraps Codex CLI's built-in image generation (`gpt-image-2`, aka ImageGen v2). Codex doesn't
have a dedicated `--image-gen` flag — it triggers off natural-language intent or the literal
token `$imagegen` in the prompt. This skill makes that reliable by:

1. Always including `$imagegen` so the image path fires deterministically
2. Granting Codex write access to the output directory via `--add-dir`
3. Telling Codex the exact absolute output filename so the result is findable

Sister skills: `nanobanana-image-gen` (Gemini-backed) and `ask-codex` (text-only Codex
queries). Use this one specifically when the user wants Codex's image model — it tends
toward photographic / illustrative output with strong text rendering.

## Capabilities

- **Text-to-image** — "generate a hero banner of …"
- **Image-to-image edit** — single source + a transform ("remove the background")
- **Multi-reference composition** — 2+ refs combined ("put the logo from image 1 onto the
  device in image 2, matching the perspective")

All three use the same command shape; the only difference is how many `-i <file>` flags
are passed and how the prompt refers to them.

## Aspect ratio and resolution

Codex doesn't expose a `--size` flag — `gpt-image-2` picks dimensions from your prompt.
Empirically:

- **State the ratio explicitly as `W:H`** ("1:3 portrait", "16:9 landscape", "1:1 square")
  to get that exact ratio. Inches and "letter sized" produce a close-but-rounded match.
- **Default behavior** (no size mentioned): tall outputs land around 1024–1100 wide ×
  1400–1500 tall — roughly 0.75:1.
- **Long-edge ceiling**: at least **2172 px** is reachable if you ask for it. The actual
  cap isn't published; `gpt-image-2`'s docs aren't public yet. To request high res, write
  "produce this at the highest resolution gpt-image-2 supports — target ~2K on the long
  edge" in the prompt. Don't promise the user a specific pixel size — verify with `sips`
  after the run.
- **Verify dimensions** after every run that cares about size:
  ```bash
  sips -g pixelWidth -g pixelHeight "$OUT_FILE"
  ```
- **Extreme ratios work** — 1:3 (bookmark), 1:4, 21:9 ultrawide are all honored. The
  model adjusts the long edge accordingly so the requested ratio is exact.
- **No upscaling step**: if you need higher resolution than the model gives, run a
  separate upscaler — Codex itself doesn't upscale.

## Default output location

`~/Downloads/codex-img-<UTC-timestamp>.png` unless the user names a specific path. The
absolute path matters — Codex saves to an arbitrary location otherwise, and the file
becomes hard to surface. Pass it both via `--add-dir` (CLI permission) AND in the prompt
text (instruction to save there).

## Command shape

Build a per-invocation block that picks the output path, then runs `codex exec`:

```bash
OUT_DIR="$HOME/Downloads"
TS=$(date -u +%Y%m%dT%H%M%SZ)
OUT_FILE="$OUT_DIR/codex-img-$TS.png"
CODEX_OUT="/tmp/codex-response-${$}-${RANDOM}.txt"
```

Note on temp filenames: same convention as `ask-codex` — `${$}` (shell PID) plus
`$RANDOM` so parallel calls don't collide. Don't use `mktemp` with an `XXXXXX` template;
prior runs leave literal `XXXXXX` files behind that cause it to fail.

### Text-to-image

```bash
codex exec \
  -s workspace-write \
  --add-dir "$OUT_DIR" \
  --skip-git-repo-check \
  -o "$CODEX_OUT" \
  "\$imagegen Generate an image based on the prompt below and save the
final PNG to EXACTLY this path: $OUT_FILE

Prompt: <user's image description verbatim>"
```

Two things that trip people up here:

- **`\$imagegen` must be escaped** in a double-quoted bash string, otherwise the shell
  expands it to an empty variable and Codex never sees the trigger token. Single-quoting
  the whole prompt is fine too.
- **`--skip-git-repo-check`** — `~/Downloads` isn't a git repo and Codex refuses to run
  outside one without this flag.

### Image-to-image edit (one reference)

```bash
codex exec \
  -s workspace-write \
  --add-dir "$OUT_DIR" \
  --skip-git-repo-check \
  -i "$REF_IMAGE" \
  -o "$CODEX_OUT" \
  "\$imagegen Transform the attached image as follows: <user's transform>.

Save the final PNG to EXACTLY this path: $OUT_FILE"
```

### Multi-reference composition

Pass `-i` once per reference; address them by position in the prompt:

```bash
codex exec \
  -s workspace-write \
  --add-dir "$OUT_DIR" \
  --skip-git-repo-check \
  -i "$LOGO" -i "$MOCKUP" \
  -o "$CODEX_OUT" \
  "\$imagegen Compose a single image: place the logo from the first attached
image onto the device screen in the second attached image. Match the perspective,
scale, and lighting of the device.

Save the final PNG to EXACTLY this path: $OUT_FILE"
```

## Resolving the reference images

- **Pasted into the conversation**: already on disk — Claude Code surfaces the path. Pass
  it straight to `-i`.
- **Referred to by name** ("the screenshot from earlier"): confirm the absolute path
  before running. Don't guess.
- **URL**: download first, since `-i` only takes local paths.
  ```bash
  REF=/tmp/codex-ref-${$}-${RANDOM}.png
  curl -fsSL -o "$REF" "$URL"
  ```

## After the run

1. Read `$CODEX_OUT` — it has Codex's narrative response (any notes about choices made,
   limitations hit, etc.). Surface anything notable.
2. Verify the file landed: `ls -lh "$OUT_FILE"`. If missing, see the next paragraph.
3. Tell the user the absolute path.
4. Display the image inline by reading it with the Read tool — Claude Code renders PNG/JPG
   previews directly.

### Where Codex actually saves images (recovery path)

Codex always writes the raw render to `~/.codex/generated_images/<session-id>/ig_*.png`
first, then copies it to whatever path you specified in the prompt. This means: even if
the destination copy fails for any reason, the image still exists at the canonical
location. To recover the most recent generation for a known session:

```bash
ls -t "$HOME/.codex/generated_images/$SESSION"/ig_*.png | head -1
```

Or, if you don't know the session id, the newest render across all sessions:

```bash
find "$HOME/.codex/generated_images" -name 'ig_*.png' -print0 \
  | xargs -0 ls -t | head -1
```

## Iterations and variations

When the user says "now make it more X" or "give me a darker version", resume the prior
Codex session instead of starting fresh — the image-gen model keeps prior visual context,
which produces more coherent variants than re-prompting from scratch.

To capture the session id, run the initial call with `--json` redirected to a file
(don't pipe through `head -1` — SIGPIPE kills Codex before it writes `-o`):

```bash
CODEX_JSON="/tmp/codex-json-${$}-${RANDOM}.txt"
codex exec --json -s workspace-write --add-dir "$OUT_DIR" --skip-git-repo-check \
  -o "$CODEX_OUT" \
  "\$imagegen <prompt> ... save to: $OUT_FILE" \
  > "$CODEX_JSON" 2>/dev/null

head -1 "$CODEX_JSON" \
  | python3 -c "import sys,json; print(json.load(sys.stdin).get('thread_id',''))" \
  > /tmp/codex-image-last-session.txt
```

For each follow-up (note: `resume` rejects both `-s` and `--add-dir` — it inherits the
original sandbox AND its writable dirs, so as long as the first call passed
`--add-dir "$OUT_DIR"`, follow-ups can write there too. `--skip-git-repo-check` IS
accepted on resume):

```bash
SESSION=$(cat /tmp/codex-image-last-session.txt)
NEW_OUT="$OUT_DIR/codex-img-$(date -u +%Y%m%dT%H%M%SZ)-v2.png"
codex exec resume \
  --skip-git-repo-check \
  -o "$CODEX_OUT" \
  "$SESSION" \
  "\$imagegen Same subject, but with dramatic rim lighting from the left.
Save to EXACTLY: $NEW_OUT"
```

When you resume with an image-edit prompt ("same flyer but X"), Codex auto-detects this
and switches to "built-in edit mode" — it loads the prior render as the edit target and
modifies only what you asked. This produces much more coherent variants than a fresh
text-to-image call. Strongly prefer resume for "now make it more X" flows.

## Billing

By default, image generation counts against the user's Codex usage quota and burns it
roughly 3–5× faster than a typical turn. Fine for one-offs and small batches.

For larger batches (≥10 images), or if the user is bumping into Codex usage limits,
suggest `OPENAI_API_KEY` — Codex will route generation through the OpenAI API and bill
per-image instead:

```bash
OPENAI_API_KEY="sk-..." codex exec ...
```

Don't set this automatically. Let the user opt in. The relevant key is in the user's own
OpenAI account, not anything this project provides.

## Timeout

Image generation takes ~30–90s for one image, longer for multi-reference composition.
Use a 300-second Bash timeout for single-image runs, 600s for batches or composition.

## Common failure modes

- **`$imagegen` was expanded by the shell** → Codex describes the image in text instead of
  generating it. Escape as `\$imagegen` in double quotes, or single-quote the prompt.
- **File missing after a "successful" run** → either `--add-dir` was omitted (Codex saved
  to cwd as a fallback) or it picked its own filename. Always pass `--add-dir "$OUT_DIR"`
  AND specify the absolute target in the prompt with the word "EXACTLY".
- **"I can't write outside the workspace"** → `--add-dir` missing. Mentioning the path in
  the prompt isn't enough; the CLI flag is what grants the permission.
- **"Not a git repository"** → add `--skip-git-repo-check`. Required for `~/Downloads`.
- **Reference image errors** → `-i` accepts local file paths only. URLs and base64 do not
  work — download first to `/tmp/`.
- **Codex quota exhausted mid-batch** → switch to `OPENAI_API_KEY` and re-run the
  remaining items.

## Sandbox

Always `-s workspace-write` for this skill — Codex needs to write the PNG. Never
`danger-full-access` for image generation; there's no reason to grant more than write
access to the output directory.
