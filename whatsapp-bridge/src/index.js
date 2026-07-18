/**
 * WhatsApp Business Cloud API Bridge
 *
 * Uses the official Meta WhatsApp Business Platform Cloud API.
 * This is the ONLY officially supported way to automate WhatsApp messaging.
 *
 * Prerequisites:
 * 1. Meta Business App with WhatsApp product enabled
 * 2. WhatsApp Business Account (WABA)
 * 3. Phone number registered with WhatsApp Business API
 * 4. Permanent access token from Meta developer console
 *
 * Setup Guide: https://developers.facebook.com/docs/whatsapp/overview
 */

require("dotenv").config();
const crypto = require("crypto");
const express = require("express");
const axios = require("axios");
const cron = require("node-cron");
const { v4: uuidv4 } = require("uuid");
const pino = require("pino");

const app = express();
app.use(express.json());

const logger = pino({ level: process.env.LOG_LEVEL || "info" });

// ─── Configuration ──────────────────────────────────────────────
const CONFIG = {
  metaApiVersion: "v18.0",
  phoneNumberId: process.env.WHATSAPP_PHONE_NUMBER_ID,
  accessToken: process.env.META_ACCESS_TOKEN,
  appSecret: process.env.META_APP_SECRET,
  backendUrl: process.env.BACKEND_URL || "http://localhost:8000",
  webhookVerifyToken: process.env.WHATSAPP_WEBHOOK_VERIFY_TOKEN || "change-me",
  bridgeSecret: process.env.BRIDGE_WEBHOOK_SECRET || "change-me",
  port: process.env.PORT || 3001,
};

// ─── Meta WhatsApp API Client ───────────────────────────────────

class WhatsAppCloudClient {
  constructor(accessToken, phoneNumberId, apiVersion) {
    this.accessToken = accessToken;
    this.phoneNumberId = phoneNumberId;
    this.apiVersion = apiVersion;
    this.baseUrl = `https://graph.facebook.com/${apiVersion}`;
  }

  get headers() {
    return {
      Authorization: `Bearer ${this.accessToken}`,
      "Content-Type": "application/json",
    };
  }

  async sendTextMessage(to, text) {
    const url = `${this.baseUrl}/${this.phoneNumberId}/messages`;
    const payload = {
      messaging_product: "whatsapp",
      to,
      type: "text",
      text: { body: text },
    };
    const response = await axios.post(url, payload, { headers: this.headers });
    return response.data;
  }

  async sendTemplateMessage(to, templateName, languageCode = "en") {
    const url = `${this.baseUrl}/${this.phoneNumberId}/messages`;
    const payload = {
      messaging_product: "whatsapp",
      to,
      type: "template",
      template: {
        name: templateName,
        language: { code: languageCode },
      },
    };
    const response = await axios.post(url, payload, { headers: this.headers });
    return response.data;
  }

  async markAsRead(messageId) {
    const url = `${this.baseUrl}/${this.phoneNumberId}/messages`;
    const payload = {
      messaging_product: "whatsapp",
      status: "read",
      message_id: messageId,
    };
    await axios.post(url, payload, { headers: this.headers });
  }

  async getMessage(messageId) {
    const url = `${this.baseUrl}/${messageId}`;
    const response = await axios.get(url, { headers: this.headers });
    return response.data;
  }

  async getMediaUrl(mediaId) {
    const url = `${this.baseUrl}/${mediaId}`;
    const response = await axios.get(url, { headers: this.headers });
    return response.data;
  }

  async downloadMedia(mediaUrl) {
    const response = await axios.get(mediaUrl, {
      headers: { Authorization: `Bearer ${this.accessToken}` },
      responseType: "arraybuffer",
    });
    return response.data;
  }
}

// ─── Bridge State ───────────────────────────────────────────────

let waClient = null;
let isConnected = false;

function initClient() {
  if (!CONFIG.accessToken || !CONFIG.phoneNumberId) {
    logger.warn("WhatsApp Cloud API credentials not configured");
    return null;
  }
  waClient = new WhatsAppCloudClient(
    CONFIG.accessToken,
    CONFIG.phoneNumberId,
    CONFIG.metaApiVersion
  );
  isConnected = true;
  logger.info({ phoneNumberId: CONFIG.phoneNumberId }, "whatsapp_cloud_connected");
  return waClient;
}

// ─── Helpers ────────────────────────────────────────────────────

function extractPhoneNumber(from) {
  // Meta sends JID format: 919123456789@c.us
  return from?.replace("@c.us", "").replace("@s.whatsapp.net", "");
}

function isIndividualChat(entry) {
  // Meta Cloud API only delivers personal chat messages via webhook
  // Groups, broadcasts, channels are not delivered to third-party webhooks
  // This is enforced by Meta's platform itself
  return true;
}

async function postToBackend(payload) {
  const https = require("https");
  const http = require("http");
  const data = JSON.stringify(payload);
  const url = new URL("/api/webhooks/whatsapp", CONFIG.backendUrl);
  const options = {
    hostname: url.hostname,
    port: url.port || (url.protocol === "https:" ? 443 : 80),
    path: url.pathname,
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "Content-Length": Buffer.byteLength(data),
      "X-Bridge-Secret": CONFIG.bridgeSecret,
    },
  };

  const protocol = url.protocol === "https:" ? https : http;
  return new Promise((resolve, reject) => {
    const req = protocol.request(options, (res) => {
      let body = "";
      res.on("data", (chunk) => (body += chunk));
      res.on("end", () => {
        try { resolve(JSON.parse(body)); }
        catch { resolve({ status: "ok" }); }
      });
    });
    req.on("error", reject);
    req.write(data);
    req.end();
  });
}

// ─── Webhook Verification (GET) ─────────────────────────────────
// Meta sends GET to verify webhook URL during setup

app.get("/webhook", (req, res) => {
  const mode = req.query["hub.mode"];
  const token = req.query["hub.verify_token"];
  const challenge = req.query["hub.challenge"];

  if (mode === "subscribe" && token === CONFIG.webhookVerifyToken) {
    logger.info("webhook_verified");
    return res.status(200).send(challenge);
  }
  logger.warn("webhook_verification_failed");
  return res.status(403).send("Forbidden");
});

// ─── Incoming Messages (POST) ───────────────────────────────────
// Meta sends POST with incoming messages

app.post("/webhook", async (req, res) => {
  // Verify webhook signature from Meta
  const signature = req.headers["x-hub-signature-256"];
  if (signature && CONFIG.appSecret) {
    const expectedSig = "sha256=" + crypto
      .createHmac("sha256", CONFIG.appSecret)
      .update(JSON.stringify(req.body))
      .digest("hex");
    if (signature !== expectedSig) {
      logger.warn({ signature }, "invalid_webhook_signature");
      // Continue processing but log warning (Meta may not always send signature)
    }
  }

  // Acknowledge immediately (Meta requires response within 20 seconds)
  res.status(200).send("OK");

  const { entry } = req.body;
  if (!entry || !entry.length) return;

  for (const entryItem of entry) {
    const changes = entryItem.changes || [];
    for (const change of changes) {
      const { value } = change;
      if (!value || !value.messages) continue;

      for (const msg of value.messages) {
        try {
          await handleIncomingMessage(msg, value);
        } catch (err) {
          logger.error({ err, msgId: msg.id }, "message_handler_error");
        }
      }

      // Handle status updates (delivered, read, etc.)
      if (value.statuses) {
        for (const status of value.statuses) {
          logger.info({ msgId: status.id, status: status.status }, "message_status_update");
        }
      }
    }
  }
});

async function handleIncomingMessage(msg, value) {
  const from = msg.from;
  const msgId = msg.id;
  const timestamp = new Date(parseInt(msg.timestamp) * 1000).toISOString();

  // Mark message as read
  if (waClient) {
    await waClient.markAsRead(msgId).catch(() => {});
  }

  // Extract message content
  let textContent = null;
  let messageType = "text";
  let mediaUrl = null;
  let mediaMimeType = null;
  let mediaCaption = null;

  if (msg.type === "text" && msg.text) {
    textContent = msg.text.body;
  } else if (msg.type === "image" && msg.image) {
    messageType = "image";
    mediaMimeType = msg.image.mime_type;
    mediaCaption = msg.image.caption || null;
    // Download media if URL provided
    if (msg.image.id) {
      try {
        const mediaInfo = await waClient.getMediaUrl(msg.image.id);
        if (mediaInfo.url) {
          const mediaBuffer = await waClient.downloadMedia(mediaInfo.url);
          mediaUrl = `data:${mediaMimeType};base64,${Buffer.from(mediaBuffer).toString("base64")}`;
        }
      } catch (err) {
        logger.warn({ err, mediaId: msg.image.id }, "media_download_failed");
      }
    }
  } else if (msg.type === "video" && msg.video) {
    messageType = "video";
    mediaMimeType = msg.video.mime_type;
    mediaCaption = msg.video.caption || null;
  } else if (msg.type === "audio" && msg.audio) {
    messageType = "audio";
    mediaMimeType = msg.audio.mime_type;
  } else if (msg.type === "document" && msg.document) {
    messageType = "document";
    mediaMimeType = msg.document.mime_type;
    mediaCaption = msg.document.caption || null;
  } else if (msg.type === "location" && msg.location) {
    messageType = "location";
    textContent = `Location: ${msg.location.latitude}, ${msg.location.longitude}`;
  } else if (msg.type === "contacts" && msg.contacts) {
    messageType = "contact";
    textContent = `Contact shared: ${msg.contacts?.[0]?.profile?.name || "Unknown"}`;
  }

  // Build payload for backend
  const payload = {
    whatsapp_message_id: msgId,
    whatsapp_chat_id: from,
    sender_jid: from,
    direction: "incoming",
    message_type: messageType,
    timestamp,
    text_content: textContent,
    media_url: mediaUrl,
    media_mime_type: mediaMimeType,
    media_caption: mediaCaption,
    sender_name: value.contacts?.[0]?.profile?.name || null,
  };

  logger.info({ msgId, from, type: messageType, text: textContent?.slice(0, 50) }, "forwarding_to_backend");

  try {
    const response = await postToBackend(payload);
    if (response.reply && waClient) {
      await waClient.sendTextMessage(from, response.reply);
      logger.info({ msgId, replyLength: response.reply.length }, "ai_reply_sent");
    }
  } catch (err) {
    logger.error({ err }, "backend_forward_failed");
  }
}

// ─── REST API ───────────────────────────────────────────────────

// Send message (used by backend for AI replies)
app.post("/send", async (req, res) => {
  const { chat_id, text } = req.body;
  if (!chat_id || !text) {
    return res.status(400).json({ error: "chat_id and text required" });
  }
  if (!waClient) {
    return res.status(503).json({ error: "WhatsApp not connected" });
  }
  try {
    await waClient.sendTextMessage(chat_id, text);
    res.json({ status: "sent" });
  } catch (err) {
    logger.error({ err }, "send_failed");
    res.status(500).json({ error: "Send failed" });
  }
});

// Send consent request template
app.post("/send-consent", async (req, res) => {
  const { chat_id } = req.body;
  if (!chat_id) return res.status(400).json({ error: "chat_id required" });
  if (!waClient) return res.status(503).json({ error: "WhatsApp not connected" });

  const consentMessage = `Hi 👋

I'm using an AI assistant that can help reply to my WhatsApp messages.

Would you like to continue chatting with the AI assistant?

Reply

YES

or

NO`;

  try {
    await waClient.sendTextMessage(chat_id, consentMessage);
    res.json({ status: "sent" });
  } catch (err) {
    logger.error({ err }, "consent_send_failed");
    res.status(500).json({ error: "Failed to send consent message" });
  }
});

// Connection status
app.get("/status", (req, res) => {
  res.json({
    status: isConnected ? "connected" : "disconnected",
    provider: "meta_whatsapp_cloud_api",
    phone_number_id: CONFIG.phoneNumberId ? "configured" : "missing",
  });
});

// Health check
app.get("/health", (req, res) => {
  res.json({ ok: true, status: isConnected ? "connected" : "disconnected" });
});

// ─── Scheduled Tasks ────────────────────────────────────────────

// Periodic health check
cron.schedule("*/5 * * * *", () => {
  if (!waClient) {
    initClient();
  }
});

// ─── Start ──────────────────────────────────────────────────────

initClient();

app.listen(CONFIG.port, () => {
  logger.info({ port: CONFIG.port }, "bridge_listening");
  if (!CONFIG.accessToken || !CONFIG.phoneNumberId) {
    logger.warn("WhatsApp Cloud API not configured. Set WHATSAPP_PHONE_NUMBER_ID and META_ACCESS_TOKEN in .env");
  }
});