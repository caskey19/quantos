import { useEffect, useState } from "react";
import { Workstation } from "./Workstation";

export type Session = {
  mode: string;
  live_locked: boolean;
};

export function App() {
  const [session, setSession] = useState<Session>({ mode: "paper", live_locked: true });

  useEffect(() => {
    fetch("/api/session")
      .then((response) => response.json())
      .then((payload) => setSession({ mode: payload.mode, live_locked: payload.live_locked }))
      .catch(() => setSession({ mode: "paper", live_locked: true }));
  }, []);

  const live = session.mode === "live" && !session.live_locked;
  return (
    <div className={live ? "live-mode" : ""}>
      <Workstation mode={session.mode} live={live} />
    </div>
  );
}
