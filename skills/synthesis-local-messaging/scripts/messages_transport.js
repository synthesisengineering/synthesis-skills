// SPDX-License-Identifier: Apache-2.0
// Fixed JXA program. Only an anonymous descriptor number is an argument.
function run(argv) {
    "use strict";
    ObjC.import("Foundation");
    if (argv.length !== 1 || !/^[0-9]+$/.test(argv[0]) || Number(argv[0]) < 3) throw Error("descriptor required");
    const handle = $.NSFileHandle.alloc.initWithFileDescriptor(Number(argv[0]));
    const data = handle.readDataToEndOfFile;
    const decoded = ObjC.unwrap($.NSString.alloc.initWithDataEncoding(data, $.NSUTF8StringEncoding));
    if (typeof decoded !== "string" || decoded.length > 131072) throw Error("descriptor bound");
    const packet = JSON.parse(decoded);
    const body = packet.payload.tool_input;
    const route = body.route;
    function keys(value, expected) {
        return value !== null && typeof value === "object" && !Array.isArray(value) && Object.keys(value).sort().join("|") === expected.sort().join("|");
    }
    if (!keys(packet, ["protocol", "payload", "digest", "expires_ms"]) || packet.protocol !== 1 || !/^[a-f0-9]{64}$/.test(packet.digest) || !Number.isSafeInteger(packet.expires_ms)) throw Error("packet contract");
    if (!keys(packet.payload, ["tool_name", "tool_input"]) || packet.payload.tool_name !== "synthesis.messages.send" || !keys(body, ["request_id", "destination", "text", "route"])) throw Error("payload contract");
    if (!keys(route, ["account_id", "service", "chat_id", "participant_id"]) || route.service !== "iMessage") throw Error("explicit route required");
    if (typeof body.text !== "string" || !body.text.trim() || body.text.length > 65536 || body.text.indexOf("\u0000") !== -1) throw Error("text bound");
    for (const key of Object.keys(route)) if (typeof route[key] !== "string" || !route[key] || route[key].length > 4096) throw Error("route bound");
    if (typeof body.destination !== "string" || !/^(\+[1-9][0-9]{6,14}|[^\s@]+@[^\s@]+\.[^\s@]+)$/.test(body.destination)) throw Error("recipient contract");
    function current() {
        const now = Date.now();
        if (packet.expires_ms <= now || packet.expires_ms - now > 300000) throw Error("approval expired or unbounded");
    }
    function exact(values, id, cap) {
        if (!Array.isArray(values) || values.length > cap) throw Error("selection bound");
        const selected = values.filter(value => value.id() === id);
        if (selected.length !== 1) throw Error("ambiguous route");
        return selected[0];
    }
    current();
    const messages = Application("Messages");
    const account = exact(messages.accounts(), route.account_id, 64);
    if (account.enabled() !== true || account.connectionStatus() !== "connected" || account.serviceType() !== "iMessage") throw Error("account unavailable");
    const chat = exact(account.chats(), route.chat_id, 4096);
    if (chat.account().id() !== route.account_id) throw Error("chat account changed");
    const participants = chat.participants();
    if (!Array.isArray(participants) || participants.length !== 1) throw Error("one recipient required");
    const participant = exact(participants, route.participant_id, 1);
    if (participant.account().id() !== route.account_id || participant.handle() !== body.destination) throw Error("participant route changed");
    current(); // Final check after potentially slow account and recipient resolution.
    messages.send(body.text, {to: chat}); // Exactly one call; no fallback or retry.
    return JSON.stringify({protocol: 1, request_digest: packet.digest, phase: "dispatched"});
}
