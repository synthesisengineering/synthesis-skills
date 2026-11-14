// SPDX-License-Identifier: Apache-2.0
// Fixed read-only JXA program: list existing chats for one destination. It never sends, creates a chat or
// changes a setting. One argument, a handle: the one-to-one iMessage chats with it. Two arguments, "members"
// and a JSON list of handles: the iMessage and SMS chats, group or one-to-one, whose members are exactly those.
function run(argv) {
    "use strict";
    const HANDLE = /^(\+[1-9][0-9]{6,14}|[^\s@]+@[^\s@]+\.[^\s@]+)$/;
    let wanted = null;
    if (argv.length === 2 && argv[0] === "members") {
        wanted = JSON.parse(argv[1]);
        if (!Array.isArray(wanted) || wanted.length < 1 || wanted.length > 32 || new Set(wanted).size !== wanted.length
            || wanted.some(h => typeof h !== "string" || !HANDLE.test(h))) throw Error("members contract");
        wanted = wanted.slice().sort();
    } else if (argv.length !== 1 || !HANDLE.test(argv[0])) throw Error("recipient contract");
    const accounts = Application("com.apple.MobileSMS").accounts();
    if (!Array.isArray(accounts) || accounts.length > 64) throw Error("selection bound");
    const routes = [];
    for (const account of accounts) {
        let service;
        try { service = account.serviceType(); } catch (error) { continue; } // an account Messages cannot describe is never a route
        if (wanted ? service !== "iMessage" && service !== "SMS" : service !== "iMessage") continue; // never RCS; SMS only by members
        const usable = account.enabled() === true && account.connectionStatus() === "connected";
        const chats = account.chats();
        if (!Array.isArray(chats) || chats.length > 4096) throw Error("selection bound");
        for (const chat of chats) {
            const participants = chat.participants();
            if (!Array.isArray(participants) || participants.length > 64) continue;
            if (!wanted) {
                if (participants.length !== 1 || participants[0].handle() !== argv[0]) continue; // no group sends by handle
                routes.push({account_id: account.id(), usable: usable, chat_id: chat.id(), participant_id: participants[0].id()});
                continue;
            }
            const members = participants.map(p => ({id: p.id(), handle: p.handle()})).sort((a, b) => a.handle < b.handle ? -1 : 1);
            if (members.length !== wanted.length || members.some((m, i) => m.handle !== wanted[i])) continue; // exactly these people
            routes.push({account_id: account.id(), service: service, usable: usable, chat_id: chat.id(), participants: members});
        }
    }
    return JSON.stringify({protocol: 1, destination: wanted || argv[0], routes: routes});
}
