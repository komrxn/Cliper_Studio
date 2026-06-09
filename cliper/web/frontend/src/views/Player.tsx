import { memo, useEffect } from "react";
import { MediaPlayer, MediaProvider, type MediaPlayerInstance } from "@vidstack/react";
import { defaultLayoutIcons, DefaultVideoLayout } from "@vidstack/react/player/layouts/default";
import "@vidstack/react/player/styles/default/theme.css";
import "@vidstack/react/player/styles/default/layouts/video.css";

interface Props {
  src: string;
  title?: string;
  startAt?: number; // restore the playhead when returning to Studio
  playerRef: React.RefObject<MediaPlayerInstance>;
  onTime: (t: number) => void;
}

/**
 * Vidstack player (replaces the raw <video>). Reports time up and exposes the instance via
 * `playerRef` so the timeline can seek it (`playerRef.current.currentTime = t`).
 *
 * IMPORTANT: this is wrapped in `memo` and takes `src` as a STRING. Passing a fresh
 * `{src,type}` object (or re-rendering on every timeupdate) makes Vidstack reload the source,
 * which snaps playback back to 0:00 and breaks seeking. Keep all props referentially stable.
 */
function PlayerImpl({ src, title, startAt = 0, playerRef, onTime }: Props) {
  useEffect(() => {
    const p = playerRef.current;
    if (!p) return;
    let restored = false;
    // fire only on real time changes (avoids churn from unrelated state updates)
    return p.subscribe(({ currentTime, canPlay }) => {
      // Restore the playhead on return — but ONLY if the user hasn't already seeked
      // (currentTime still ~0). Never override a user seek that raced canPlay.
      if (!restored && canPlay && startAt > 1) {
        restored = true;
        if (currentTime < 1) p.currentTime = startAt;
      }
      onTime(currentTime);
    });
    // startAt intentionally excluded: it's a one-shot restore captured at mount/src change
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [playerRef, onTime, src]);

  return (
    <MediaPlayer
      ref={playerRef}
      title={title}
      src={src}
      aspectRatio="16/9"
      load="eager"
      playsInline
      className="w-full overflow-hidden rounded-xl bg-black"
    >
      <MediaProvider />
      <DefaultVideoLayout icons={defaultLayoutIcons} />
    </MediaPlayer>
  );
}

// Re-render only when the source actually changes — not on every timeupdate from the parent.
export default memo(PlayerImpl, (a, b) => a.src === b.src && a.title === b.title);
