"""aiqa — pre-upload AI quality gate (multimodal).

For each captioned clip, sends the transcript + a few sampled frames to OpenAI and asks whether
it is genuinely postable (hook, coherence, complete thought, visual clarity). Clips below the
threshold are dropped before we waste renders on per-account variants.
"""
from __future__ import annotations

from ..pipeline import Context
from ..utils import ffmpeg, llm

SYSTEM = (
    "You are a fair but selective short-form content critic. Judge whether a vertical clip is "
    "worth posting: does it have a hook, a coherent self-contained moment, and clear visuals? "
    "Reward genuine emotion, stakes, humor, or surprise; penalize mid-sentence fragments, "
    "ad/sponsor reads, and dead air. Score 0..1 (0.6+ = post, 0.4-0.6 = borderline, <0.4 = skip). "
    "Don't demand perfection."
)


def run(ctx: Context) -> Context:
    cfg = ctx.niche.get("qa", {})
    threshold = float(cfg.get("threshold", 0.45))
    keep_min = int(cfg.get("keep_min", 0))
    model = cfg.get("model")
    frame_dir = ctx.work_dir / "qa_frames"

    for clip in ctx.clips:
        clip.qa = _judge(clip, model, frame_dir)
        tag = "keep" if _keep(clip.qa, threshold) else "drop"
        print(f"  {clip.id}: {tag} ({clip.qa.get('score')}) {str(clip.qa.get('reason',''))[:60]}")

    kept = [c for c in ctx.clips if _keep(c.qa, threshold)]
    if len(kept) < keep_min:   # never ship nothing when a floor is configured
        kept = sorted(ctx.clips, key=lambda c: llm.as_float(c.qa.get("score")), reverse=True)[:keep_min]
    print(f"  QA kept {len(kept)}/{len(ctx.clips)} (threshold {threshold}, keep_min {keep_min})")
    ctx.clips = kept
    return ctx


def _keep(qa: dict, threshold: float) -> bool:
    """Robust keep decision (coerces 'false'/null model outputs to real bool/float)."""
    return llm.as_bool(qa.get("postable")) and llm.as_float(qa.get("score")) >= threshold


def _judge(clip, model, frame_dir):
    base = clip.current_path()
    info = ffmpeg.probe(base)
    frames = []
    for i, frac in enumerate((0.1, 0.5, 0.85)):
        fp = frame_dir / f"{clip.id}_{i}.jpg"
        ffmpeg.extract_frame(base, info.duration * frac, fp, width=360)
        frames.append(fp)
    content = [
        llm.text_block(
            "Decide if this short clip is worth posting. Judge BOTH the spoken content and the "
            'frames. Respond with JSON {"postable": bool, "score": 0..1, "reason": str}.\n\n'
            f"TRANSCRIPT: {clip.text or '(no speech)'}"
        ),
        *[llm.image_block(f) for f in frames],
    ]
    return llm.chat_json(
        [{"role": "system", "content": SYSTEM}, {"role": "user", "content": content}],
        model=model,
    )
