"use strict";
// เก็บ token ในตัวแปรเท่านั้น ไม่เขียนลง URL, cookie หรือ localStorage
let token = "";
let refreshing = false;
let online = false;
let printing = false;
let clearing = false;
let session = 0;
let maxBytes = 33554432;
const $ = (id) => document.getElementById(id);
function notice(message, kind = "") { $("notice").textContent = message; $("notice").className = kind; }
function availability() {
  $("print-button").disabled = printing || !online || !$("printer").value;
  $("clear-button").disabled = clearing || !online || !$("clear-printer").value;
}
async function call(path, options = {}) {
  const headers = new Headers(options.headers || {});
  headers.set("Authorization", `Bearer ${token}`);
  const response = await fetch(path, {...options, headers, cache: "no-store"});
  const body = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(`HTTP ${response.status}: ${typeof body.detail === "string" ? body.detail : "ตรวจข้อมูลและลองใหม่"}`);
  return body;
}
function fillQueues(queues) {
  for (const id of ["printer", "clear-printer"]) {
    const select = $(id), previous = select.value;
    select.replaceChildren();
    if (!queues.length) select.add(new Option("ยังไม่มีคิวพิมพ์ — เพิ่มใน CUPS ก่อน", ""));
    for (const queue of queues) select.add(new Option(queue.name, queue.name));
    if (queues.some((queue) => queue.name === previous)) select.value = previous;
  }
}
async function refresh() {
  if (!token || refreshing) return;
  refreshing = true;
  const currentSession = session;
  try {
    const data = await call("/status");
    if (currentSession !== session) return;
    online = data.scheduler.exit_code === 0 && data.scheduler.output.includes("scheduler is running");
    $("connection").textContent = online ? "เชื่อมต่อแล้ว" : "CUPS ไม่พร้อม";
    $("connection").className = online ? "badge online" : "badge";
    $("cups-state").textContent = online ? "พร้อม" : "ไม่พร้อม";
    $("queue-count").textContent = data.printers.length;
    $("job-count").textContent = data.jobs.exit_code === 0 ? data.jobs.output.split("\n").filter(Boolean).length : "—";
    $("usb-count").textContent = data.lsusb.output.split("\n").filter((line) => line.startsWith("Bus ")).length;
    $("lpstat").textContent = data.lpstat.output || "ยังไม่มีคิวพิมพ์";
    $("lsusb").textContent = data.lsusb.output || "ไม่พบอุปกรณ์ USB";
    maxBytes = data.max_upload_bytes;
    $("upload-limit").textContent = `ไฟล์สูงสุด ${Math.floor(maxBytes / 1048576)} MiB ต่อครั้ง`;
    $("updated").textContent = `อัปเดต ${new Date().toLocaleTimeString("th-TH")} · ตรวจใหม่ทุก 15 วินาที`;
    fillQueues(data.printers);
    const list = $("printers"); list.replaceChildren();
    if (!data.printers.length) { const p = document.createElement("p"); p.textContent = "ยังไม่มีคิวพิมพ์ เพิ่มเครื่องพิมพ์ใน CUPS ที่ https://IP-กล่อง:631"; list.append(p); }
    for (const printer of data.printers) {
      const row = document.createElement("div"); row.className = "printer-row";
      const name = document.createElement("span"); name.className = "printer-name"; name.textContent = printer.name;
      if (printer.usb) { const tag = document.createElement("small"); tag.textContent = "USB"; name.append(tag); }
      const state = document.createElement("span"); state.className = `state ${printer.state}`;
      state.textContent = ({disabled:"Paused", printing:"กำลังพิมพ์", idle:"พร้อม", unknown:"ไม่ทราบ"})[printer.state];
      row.append(name, state); list.append(row);
    }
  } catch (error) {
    if (currentSession !== session) return;
    online = false;
    $("connection").textContent = "เชื่อมต่อไม่ได้"; $("connection").className = "badge";
    $("cups-state").textContent = "—";
    notice(error.message, "error");
  } finally { refreshing = false; availability(); }
}
$("login-form").addEventListener("submit", async (event) => {
  event.preventDefault(); session++; token = $("token").value.trim(); $("token").value = "";
  notice("กำลังเชื่อมต่อ…"); await refresh();
  if (online) notice("เชื่อมต่อพร้อมใช้งานแล้ว", "success");
});
$("logout").addEventListener("click", () => {
  session++; token = ""; online = false; $("token").value = "";
  $("connection").textContent = "ออกจากระบบแล้ว"; $("connection").className = "badge";
  for (const id of ["cups-state", "queue-count", "job-count", "usb-count", "lpstat", "lsusb"]) $(id).textContent = "—";
  $("printers").replaceChildren(); fillQueues([]); availability(); notice("ออกจากระบบแล้ว");
});
$("refresh").addEventListener("click", refresh);
$("format").addEventListener("change", () => {
  const pdf = $("format").value === "pdf";
  $("file").accept = pdf ? "application/pdf,.pdf" : "";
  $("duplex").disabled = !pdf; if (!pdf) $("duplex").checked = false;
});
$("print-form").addEventListener("submit", async (event) => {
  event.preventDefault(); if (!online) return;
  const file = $("file").files[0]; if (!file) return;
  if (file.size > maxBytes) { notice("ไฟล์เกินขนาดที่เซิร์ฟเวอร์อนุญาต", "error"); return; }
  const format = $("format").value;
  const currentSession = session;
  const query = new URLSearchParams({printer: $("printer").value, copies: $("copies").value, duplex: $("duplex").checked});
  printing = true; availability(); notice("กำลังส่งไฟล์ กรุณารอ…");
  try {
    const result = await call(`/print/${format}?${query}`, {method:"POST", headers:{"Content-Type":format === "pdf" ? "application/pdf" : "application/octet-stream"}, body:file});
    if (currentSession !== session) return;
    notice(`ส่งเข้าคิวแล้ว: ${result.cups_response}`, "success"); $("file").value = ""; await refresh();
  } catch (error) { if (currentSession === session) notice(`${error.message} · ตรวจคิวก่อนส่งซ้ำ`, "error"); }
  finally { printing = false; availability(); }
});
$("clear-form").addEventListener("submit", async (event) => {
  event.preventDefault(); if (!online) return;
  const printer = $("clear-printer").value;
  const currentSession = session;
  if (!window.confirm(`ยกเลิกทุกงานในคิว ${printer} รวมงานของผู้ใช้อื่น?`)) return;
  clearing = true; availability();
  try {
    await call(`/queue/clear?${new URLSearchParams({printer})}`, {method:"POST", headers:{"Content-Type":"application/json"}, body:JSON.stringify({confirm:true})});
    if (currentSession !== session) return;
    notice(`ยกเลิกงานในคิว ${printer} แล้ว`, "success"); await refresh();
  } catch (error) { if (currentSession === session) notice(error.message, "error"); }
  finally { clearing = false; availability(); }
});
setInterval(refresh, 15000);
