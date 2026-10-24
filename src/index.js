export default {
  async fetch(request, env) {
    const url = new URL(request.url);

    if (url.pathname === "/") {
      return new Response(
        "BDG Period Analyzer service is online.",
        { headers: { "content-type": "text/plain" } }
      );
    }

    if (url.pathname === "/health") {
      return Response.json({ status: "ok" });
    }

    // Telegram sends webhook updates to /telegram.
    if (url.pathname === "/telegram" && request.method === "POST") {
      const secret = request.headers.get(
        "X-Telegram-Bot-Api-Secret-Token"
      );

      if (!env.TELEGRAM_WEBHOOK_SECRET ||
          secret !== env.TELEGRAM_WEBHOOK_SECRET) {
        return new Response("Unauthorized", { status: 401 });
      }

      const update = await request.json();
      const message = update.message;
      const chatId = message?.chat?.id;
      const text = message?.text?.trim() || "";

      if (!chatId || !text.startsWith("/")) {
        return new Response("OK");
      }

      let reply;

      switch (text.split(/\s+/)[0].split("@")[0]) {
        case "/start":
          reply =
            "BDG Period Analyzer is online.\n\n" +
            "/help — show commands\n" +
            "/health — check service status\n\n" +
            "This starter does not connect to BDG or place bets.";
          break;

        case "/help":
          reply =
            "Available commands:\n" +
            "/start — start the bot\n" +
            "/help — help\n" +
            "/health — service status";
          break;

        case "/health":
          reply = "Service status: online.";
          break;

        default:
          reply = "Unknown command. Send /help.";
      }

      const response = await fetch(
        `https://api.telegram.org/bot${env.TELEGRAM_BOT_TOKEN}/sendMessage`,
        {
          method: "POST",
          headers: { "content-type": "application/json" },
          body: JSON.stringify({
            chat_id: chatId,
            text: reply
          })
        }
      );

      if (!response.ok) {
        console.error("Telegram sendMessage failed:", response.status);
      }

      return new Response("OK");
    }

    return new Response("Not found", { status: 404 });
  }
};
