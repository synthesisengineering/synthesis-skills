// SPDX-License-Identifier: Apache-2.0
// Fixed read-only JXA program: list the existing one-to-one iMessage chats with one handle.
// The only argument is the destination handle. It never sends, creates a chat or changes a setting.
function run(argv) {
    "use strict";
    if (argv.length !== 1 || !/^(\+[1-9][0-9]{6,14}|[^\s@]+@[^\s@]+\.[^\s@]+)$/.test(argv[0])) throw Error("recipient contract");
    const destination = argv[0];
    const accounts = Application("Messages").accounts();
    if (!Array.isArray(accounts) || accounts.length > 64) throw Error("selection bound");
    const routes = [];
    for (const account of accounts) {
        if (account.serviceType() !== "iMessage") continue; // no SMS or RCS route, ever
        const usable = account.enabled() === true && account.connectionStatus() === "connected";
        const chats = account.chats();
        if (!Array.isArray(chats) || chats.length > 4096) throw Error("selection bound");
        for (const chat of chats) {
            const participants = chat.participants();
            if (!Array.isArray(participants) || participants.length !== 1) continue; // no group sends
            if (participants[0].handle() !== destination) continue;
            routes.push({account_id: account.id(), usable: usable, chat_id: chat.id(), participant_id: participants[0].id()});
        }
    }
    return JSON.stringify({protocol: 1, destination: destination, routes: routes});
}
