import { createRoot } from "react-dom/client";
import { App } from "./App";
import { createClient } from "./api/client";
import { createBrowserAudio } from "./audio/browserAudio";
import "./styles.css";

const root = document.getElementById("root");
if (root === null) {
  throw new Error("The page has no #root element");
}
// No StrictMode: its double mount would close the AudioContext the mixer is using.
createRoot(root).render(<App client={createClient()} createAudio={createBrowserAudio} />);
