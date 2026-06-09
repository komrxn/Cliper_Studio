import { useEffect } from "react";
import { MediaPlayer, MediaProvider, type MediaPlayerInstance } from "@vidstack/react";
import { defaultLayoutIcons, DefaultVideoLayout } from "@vidstack/react/player/layouts/default";
import "@vidstack/react/player/styles/default/theme.css";
import "@vidstack/react/player/styles/default/layouts/video.css";

interface Props {
  src: string;
  title?: string;
  playerRef: React.RefObject<MediaPlayerInstance>;
  onTime: (t: number) => void;
}

/** Vidstack player (replaces the raw <video>). Reports time up and exposes the instance via
 *  `playerRef` so the timeline can seek it (`playerRef.current.currentTime = t`). */
export default function Player({ src, title, playerRef, onTime }: Props) {
  useEffect(() => {
    const p = playerRef.current;
    if (!p) return;
    return p.subscribe(({ currentTime }) => onTime(currentTime));
  }, [playerRef, onTime, src]);

  return (
    <MediaPlayer
      ref={playerRef}
      title={title}
      src={{ src, type: "video/mp4" }}
      aspectRatio="16/9"
      crossOrigin
      playsInline
      className="w-full overflow-hidden rounded-xl bg-black"
    >
      <MediaProvider />
      <DefaultVideoLayout icons={defaultLayoutIcons} />
    </MediaPlayer>
  );
}
