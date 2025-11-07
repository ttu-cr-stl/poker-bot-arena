import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
import { useEffect, useState } from "react";
export function ControlPanel({ state, connection, onConfigChange }) {
    const [wsInput, setWsInput] = useState("");
    const status = state.status;
    useEffect(() => {
        if (!state.meta?.wsUrl && wsInput === "") {
            setWsInput("ws://127.0.0.1:8765/spectate");
        }
    }, [state.meta?.wsUrl, wsInput]);
    const applyConfig = () => {
        const next = {};
        next.wsUrl = wsInput.trim() || null;
        onConfigChange(next);
    };
    return (_jsxs("div", { className: "control-panel", children: [_jsx("h2", { children: "Config" }), _jsxs("div", { className: "control-panel__section", children: [_jsx("label", { className: "control-panel__label", children: "WS URL" }), _jsx("input", { className: "control-panel__input", placeholder: "ws://host:port/spectate", value: wsInput, onChange: (event) => setWsInput(event.target.value) })] }), _jsx("button", { className: "control-panel__button", onClick: applyConfig, type: "button", children: "Apply" }), _jsxs("div", { className: "control-panel__section", children: [_jsx("label", { className: "control-panel__label", children: "Connection" }), _jsx("span", { className: "control-panel__value", children: connection })] }), _jsxs("details", { className: "control-panel__details", children: [_jsx("summary", { children: "Status feed" }), _jsx("pre", { className: "control-panel__log", children: JSON.stringify({ mode: status?.hand_control, awaiting: status?.awaiting_manual_start, ws: state.meta?.wsUrl }, null, 2) })] })] }));
}
