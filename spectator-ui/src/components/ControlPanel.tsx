import type { ConnectionStatus, SpectatorStoreState } from "../types";
import { useEffect, useState } from "react";

interface ControlPanelProps {
  state: SpectatorStoreState;
  connection: ConnectionStatus;
  onConfigChange: (config: Partial<{ wsUrl: string | null }>) => void;
}

export function ControlPanel({ state, connection, onConfigChange }: ControlPanelProps) {
  const [wsInput, setWsInput] = useState("");
  const status = state.status;

  useEffect(() => {
    if (!state.meta?.wsUrl && wsInput === "") {
      setWsInput("ws://127.0.0.1:8765/spectate");
    }
  }, [state.meta?.wsUrl, wsInput]);

  const applyConfig = () => {
    const next: Partial<{ wsUrl: string | null }> = {};
    next.wsUrl = wsInput.trim() || null;
    onConfigChange(next);
  };

  return (
    <div className="control-panel">
      <h2>Config</h2>
      <div className="control-panel__section">
        <label className="control-panel__label">WS URL</label>
        <input
          className="control-panel__input"
          placeholder="ws://host:port/spectate"
          value={wsInput}
          onChange={(event) => setWsInput(event.target.value)}
        />
      </div>
      <button className="control-panel__button" onClick={applyConfig} type="button">
        Apply
      </button>

      <div className="control-panel__section">
        <label className="control-panel__label">Connection</label>
        <span className="control-panel__value">{connection}</span>
      </div>
      <details className="control-panel__details">
        <summary>Status feed</summary>
        <pre className="control-panel__log">
{JSON.stringify({ mode: status?.hand_control, awaiting: status?.awaiting_manual_start, ws: state.meta?.wsUrl }, null, 2)}
        </pre>
      </details>
    </div>
  );
}
