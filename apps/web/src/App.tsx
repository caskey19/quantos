import { useEffect, useState } from "react";
import { getJson } from "./client";
import { Workstation } from "./Workstation";

export type Session = {
  mode: string;
  live_locked: boolean;
  recorded?: boolean;
};

export function App() {
  const [session, setSession] = useState<Session>({ mode: "paper", live_locked: true });

  useEffect(() => {
    getJson("/api/session")
      .then((payload) =>
        setSession({
          mode: payload.mode,
          live_locked: payload.live_locked,
          recorded: Boolean(payload.recorded),
        }),
      )
      .catch(() => setSession({ mode: "paper", live_locked: true, recorded: true }));
  }, []);

  const live = session.mode === "live" && !session.live_locked;
  return (
    <div className={live ? "live-mode" : ""}>
      <Workstation mode={session.mode} live={live} recorded={Boolean(session.recorded)} />
    </div>
  );
}
