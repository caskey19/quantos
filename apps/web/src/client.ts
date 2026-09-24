export async function getJson(path: string): Promise<any> {
  if (import.meta.env.VITE_STATIC === "1") {
    return fromSnapshot(path);
  }
  try {
    const response = await fetch(path);
    if (!response.ok) throw new Error(`${path} ${response.status}`);
    return response.json();
  } catch (error) {
    try {
      return await fromSnapshot(path);
    } catch {
      throw error;
    }
  }
}

let snapshotPromise: Promise<Record<string, unknown>> | null = null;

async function fromSnapshot(path: string) {
  if (!snapshotPromise) {
    snapshotPromise = fetch(`${import.meta.env.BASE_URL}snapshot.json`).then((response) => {
      if (!response.ok) throw new Error("snapshot unavailable");
      return response.json();
    });
  }
  const snapshot = await snapshotPromise;
  if (!(path in snapshot)) throw new Error(`${path} missing from snapshot`);
  return snapshot[path];
}
