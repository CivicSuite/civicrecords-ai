
import { useState, useEffect } from "react";
import { useParams, Link } from "react-router-dom";
import { apiFetch } from "@/lib/api";
import { RichTextEditor } from "@/components/RichTextEditor";
import { StatusBadge } from "@/components/status-badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Separator } from "@/components/ui/separator";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import {
  ArrowLeft,
  Calendar,
  User,
  FileText,
  Send,
  Eye,
  CheckCircle,
  XCircle,
  Search,
  Clock,
  MessageSquare,
  Activity,
  DollarSign,
  AlertCircle,
  Info,
  Plus,
  FileEdit,
  Loader2,
} from "lucide-react";

interface RequestData {
  id: string;
  requester_name: string;
  requester_email: string;
  description: string;
  status: string;
  statutory_deadline: string | null;
  created_at: string;
  response_draft: string | null;
  review_notes: string | null;
}

interface AttachedDoc {
  id: string;
  document_id: string;
  relevance_note: string | null;
  inclusion_status: string;
  attached_at: string;
}

interface TimelineEvent {
  id: string;
  request_id: string;
  event_type: string;
  actor_id: string | null;
  actor_role: string | null;
  description: string;
  internal_note: string | null;
  created_at: string;
}

interface Message {
  id: string;
  request_id: string;
  sender_type: string;
  sender_id: string | null;
  message_text: string;
  is_internal: boolean;
  created_at: string;
}

interface FeeLineItem {
  id: string;
  request_id: string;
  description: string;
  quantity: number;
  unit_price: number;
  total: number;
  status: string;
  created_at: string;
}

interface ResponseLetter {
  id: string;
  request_id: string;
  content: string;
  edited_content: string | null;
  status: string;
  created_at: string;
  updated_at: string;
}

function formatDate(dateStr: string | null): string {
  if (!dateStr) return "Not set";
  return new Date(dateStr).toLocaleDateString();
}

function formatDateTime(dateStr: string): string {
  return new Date(dateStr).toLocaleString();
}

function formatCurrency(amount: number): string {
  return new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" }).format(amount);
}

const EVENT_TYPE_ICONS: Record<string, React.ElementType> = {
  created: Plus,
  status_changed: Activity,
  document_attached: FileText,
  message_sent: MessageSquare,
  fee_added: DollarSign,
  approved: CheckCircle,
  rejected: XCircle,
  fulfilled: Send,
};

function TimelineIcon({ eventType }: { eventType: string }) {
  const Icon = EVENT_TYPE_ICONS[eventType] ?? Info;
  return <Icon className="h-3.5 w-3.5" />;
}

const WORKFLOW_ACTIONS: Record<string, { label: string; action: string; variant: "default" | "outline"; icon: React.ElementType }[]> = {
  received: [
    { label: "Begin Search", action: "searching", variant: "default", icon: Search },
  ],
  searching: [
    { label: "Submit for Review", action: "submit-review", variant: "default", icon: Eye },
  ],
  in_review: [
    { label: "Approve", action: "approve", variant: "default", icon: CheckCircle },
    { label: "Reject", action: "reject", variant: "outline", icon: XCircle },
  ],
  drafted: [
    { label: "Submit for Review", action: "submit-review", variant: "default", icon: Eye },
  ],
  approved: [
    { label: "Mark Fulfilled", action: "sent", variant: "default", icon: Send },
  ],
};

export default function RequestDetail({ token }: { token: string }) {
  const { id } = useParams<{ id: string }>();
  const [req, setReq] = useState<RequestData | null>(null);
  const [docs, setDocs] = useState<AttachedDoc[]>([]);
  const [timeline, setTimeline] = useState<TimelineEvent[]>([]);
  const [messages, setMessages] = useState<Message[]>([]);
  const [fees, setFees] = useState<FeeLineItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [actionLoading, setActionLoading] = useState(false);

  // Message form state
  const [newMessage, setNewMessage] = useState("");
  const [isInternal, setIsInternal] = useState(false);
  const [sendingMessage, setSendingMessage] = useState(false);

  // Fee form state
  const [feeDesc, setFeeDesc] = useState("");
  const [feeQty, setFeeQty] = useState("1");
  const [feePrice, setFeePrice] = useState("");
  const [addingFee, setAddingFee] = useState(false);
  const [showFeeForm, setShowFeeForm] = useState(false);

  // Response letter state
  const [letter, setLetter] = useState<ResponseLetter | null>(null);
  const [letterContent, setLetterContent] = useState("");
  const [generatingLetter, setGeneratingLetter] = useState(false);
  const [savingLetter, setSavingLetter] = useState(false);

  const loadData = async () => {
    try {
      const [reqData, docsData, timelineData, messagesData, feesData] = await Promise.all([
        apiFetch<RequestData>(`/requests/${id}`, { token }),
        apiFetch<AttachedDoc[]>(`/requests/${id}/documents`, { token }),
        apiFetch<TimelineEvent[]>(`/requests/${id}/timeline`, { token }),
        apiFetch<Message[]>(`/requests/${id}/messages`, { token }),
        apiFetch<FeeLineItem[]>(`/requests/${id}/fees`, { token }),
      ]);
      setReq(reqData);
      setDocs(docsData);
      setTimeline(timelineData);
      setMessages(messagesData);
      setFees(feesData);
      // Load response letter (may not exist yet — 404 is fine)
      try {
        const letterData = await apiFetch<ResponseLetter>(`/requests/${id}/response-letter`, { token });
        setLetter(letterData);
        setLetterContent(letterData.edited_content ?? letterData.content ?? "");
      } catch {
        setLetter(null);
        setLetterContent("");
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { loadData(); }, [id, token]);

  const handleAction = async (action: string) => {
    setActionLoading(true);
    try {
      if (action === "searching") {
        await apiFetch(`/requests/${id}`, {
          token,
          method: "PATCH",
          body: JSON.stringify({ status: action }),
        });
      } else {
        await apiFetch(`/requests/${id}/${action}`, {
          token,
          method: "POST",
        });
      }
      await loadData();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Action failed");
    } finally {
      setActionLoading(false);
    }
  };

  const handleSendMessage = async () => {
    if (!newMessage.trim()) return;
    setSendingMessage(true);
    try {
      await apiFetch(`/requests/${id}/messages`, {
        token,
        method: "POST",
        body: JSON.stringify({ message_text: newMessage.trim(), is_internal: isInternal }),
      });
      setNewMessage("");
      const updated = await apiFetch<Message[]>(`/requests/${id}/messages`, { token });
      setMessages(updated);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to send message");
    } finally {
      setSendingMessage(false);
    }
  };

  const handleAddFee = async () => {
    if (!feeDesc.trim() || !feePrice) return;
    setAddingFee(true);
    try {
      await apiFetch(`/requests/${id}/fees`, {
        token,
        method: "POST",
        body: JSON.stringify({
          description: feeDesc.trim(),
          quantity: parseFloat(feeQty) || 1,
          unit_price: parseFloat(feePrice) || 0,
        }),
      });
      setFeeDesc("");
      setFeeQty("1");
      setFeePrice("");
      setShowFeeForm(false);
      const updated = await apiFetch<FeeLineItem[]>(`/requests/${id}/fees`, { token });
      setFees(updated);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to add fee");
    } finally {
      setAddingFee(false);
    }
  };

  const LETTER_ELIGIBLE_STATUSES = ["searching", "in_review", "drafted", "ready_for_release"];

  const handleGenerateLetter = async () => {
    setGeneratingLetter(true);
    try {
      const generated = await apiFetch<ResponseLetter>(`/requests/${id}/response-letter`, {
        token,
        method: "POST",
      });
      setLetter(generated);
      setLetterContent(generated.edited_content ?? generated.content ?? "");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to generate letter");
    } finally {
      setGeneratingLetter(false);
    }
  };

  const handleSaveLetter = async () => {
    if (!letter) return;
    setSavingLetter(true);
    try {
      const updated = await apiFetch<ResponseLetter>(`/requests/${id}/response-letter/${letter.id}`, {
        token,
        method: "PATCH",
        body: JSON.stringify({ edited_content: letterContent }),
      });
      setLetter(updated);
      setLetterContent(updated.edited_content ?? updated.content ?? "");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to save letter");
    } finally {
      setSavingLetter(false);
    }
  };

  const handleApproveLetter = async () => {
    if (!letter) return;
    setSavingLetter(true);
    try {
      const updated = await apiFetch<ResponseLetter>(`/requests/${id}/response-letter/${letter.id}`, {
        token,
        method: "PATCH",
        body: JSON.stringify({ status: "approved" }),
      });
      setLetter(updated);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to approve letter");
    } finally {
      setSavingLetter(false);
    }
  };

  if (loading) {
    return (
      <div className="space-y-6">
        <Skeleton className="h-8 w-48" />
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          <Skeleton className="h-64 lg:col-span-2" />
          <Skeleton className="h-48" />
        </div>
      </div>
    );
  }

  if (error || !req) {
    return (
      <div>
        <Link to="/requests" className="flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground mb-4">
          <ArrowLeft className="h-4 w-4" /> Back to Requests
        </Link>
        <Card className="border-destructive">
          <CardContent className="p-6">
            <p className="text-destructive">{error || "Request not found"}</p>
          </CardContent>
        </Card>
      </div>
    );
  }

  const actions = WORKFLOW_ACTIONS[req.status] || [];
  const feeTotal = fees.reduce((sum, f) => sum + f.total, 0);

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <Link to="/requests" className="flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground mb-4">
          <ArrowLeft className="h-4 w-4" /> Back to Requests
        </Link>
        <div className="flex items-center gap-3">
          <h1 className="text-page-title text-foreground">
            Request from {req.requester_name}
          </h1>
          <StatusBadge status={req.status} domain="request" />
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left column — details */}
        <div className="lg:col-span-2 space-y-6">
          <Card className="shadow-none">
            <CardHeader>
              <CardTitle className="text-lg">Request Details</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              <div className="flex items-center gap-2 text-sm">
                <User className="h-4 w-4 text-muted-foreground" />
                <span className="font-medium">Requester:</span>
                <span>{req.requester_name}</span>
                {req.requester_email && <span className="text-muted-foreground">({req.requester_email})</span>}
              </div>
              <div className="flex items-center gap-2 text-sm">
                <Calendar className="h-4 w-4 text-muted-foreground" />
                <span className="font-medium">Received:</span>
                <span>{formatDate(req.created_at)}</span>
              </div>
              <div className="flex items-center gap-2 text-sm">
                <Clock className="h-4 w-4 text-muted-foreground" />
                <span className="font-medium">Deadline:</span>
                <span>{formatDate(req.statutory_deadline)}</span>
              </div>
              <Separator />
              <p className="text-sm text-foreground">{req.description}</p>
            </CardContent>
          </Card>

          {/* Attached documents */}
          <Card className="shadow-none">
            <CardHeader>
              <CardTitle className="text-lg">Attached Documents ({docs.length})</CardTitle>
            </CardHeader>
            <CardContent>
              {docs.length === 0 ? (
                <p className="text-sm text-muted-foreground py-4 text-center">No documents attached yet.</p>
              ) : (
                <div className="space-y-2">
                  {docs.map((doc) => (
                    <div key={doc.id} className="flex items-center justify-between py-2 border-b last:border-0">
                      <div className="flex items-center gap-2">
                        <FileText className="h-4 w-4 text-muted-foreground" />
                        <span className="text-sm font-medium">
                          {doc.document_id.substring(0, 8)}...
                        </span>
                        {doc.relevance_note && (
                          <span className="text-xs text-muted-foreground">{doc.relevance_note}</span>
                        )}
                      </div>
                      <div className="flex items-center gap-3">
                        <StatusBadge status={doc.inclusion_status} domain="document" />
                        <span className="text-xs text-muted-foreground">{formatDate(doc.attached_at)}</span>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>

          {/* Timeline */}
          <Card className="shadow-none">
            <CardHeader>
              <CardTitle className="text-lg flex items-center gap-2">
                <Activity className="h-4 w-4" />
                Timeline ({timeline.length})
              </CardTitle>
            </CardHeader>
            <CardContent>
              {timeline.length === 0 ? (
                <p className="text-sm text-muted-foreground py-4 text-center">No timeline events yet.</p>
              ) : (
                <ol className="relative border-l border-border ml-3 space-y-4">
                  {timeline.map((event) => (
                    <li key={event.id} className="ml-4">
                      <span className="absolute -left-2.5 flex h-5 w-5 items-center justify-center rounded-full bg-muted border border-border text-muted-foreground">
                        <TimelineIcon eventType={event.event_type} />
                      </span>
                      <div className="flex flex-wrap items-center gap-2 mb-0.5">
                        <Badge variant="secondary" className="text-xs capitalize">
                          {event.event_type.replace(/_/g, " ")}
                        </Badge>
                        {event.actor_role && (
                          <span className="text-xs text-muted-foreground">{event.actor_role}</span>
                        )}
                        <span className="text-xs text-muted-foreground ml-auto">{formatDateTime(event.created_at)}</span>
                      </div>
                      <p className="text-sm text-foreground">{event.description}</p>
                      {event.internal_note && (
                        <p className="text-xs text-muted-foreground mt-1 italic">Note: {event.internal_note}</p>
                      )}
                    </li>
                  ))}
                </ol>
              )}
            </CardContent>
          </Card>

          {/* Messages */}
          <Card className="shadow-none">
            <CardHeader>
              <CardTitle className="text-lg flex items-center gap-2">
                <MessageSquare className="h-4 w-4" />
                Messages ({messages.length})
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              {messages.length === 0 ? (
                <p className="text-sm text-muted-foreground py-2 text-center">No messages yet.</p>
              ) : (
                <div className="space-y-3">
                  {messages.map((msg) => (
                    <div
                      key={msg.id}
                      className={`rounded-lg p-3 text-sm border ${
                        msg.is_internal
                          ? "bg-amber-50 border-amber-200 dark:bg-amber-950/20 dark:border-amber-800"
                          : "bg-muted/40 border-border"
                      }`}
                    >
                      <div className="flex items-center gap-2 mb-1">
                        <span className="font-medium capitalize">{msg.sender_type}</span>
                        {msg.is_internal && (
                          <Badge variant="outline" className="text-xs text-amber-700 border-amber-400">
                            Internal
                          </Badge>
                        )}
                        <span className="text-xs text-muted-foreground ml-auto">{formatDateTime(msg.created_at)}</span>
                      </div>
                      <p className="text-foreground">{msg.message_text}</p>
                    </div>
                  ))}
                </div>
              )}

              {/* Add message form */}
              <Separator />
              <div className="space-y-2">
                <div className="flex gap-2">
                  <Input
                    placeholder="Type a message..."
                    value={newMessage}
                    onChange={(e) => setNewMessage(e.target.value)}
                    onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); handleSendMessage(); } }}
                    disabled={sendingMessage}
                    className="flex-1"
                  />
                  <Button
                    onClick={handleSendMessage}
                    disabled={sendingMessage || !newMessage.trim()}
                    className="gap-1"
                  >
                    <Send className="h-4 w-4" />
                    Send
                  </Button>
                </div>
                <label className="flex items-center gap-2 text-xs text-muted-foreground cursor-pointer select-none">
                  <input
                    type="checkbox"
                    checked={isInternal}
                    onChange={(e) => setIsInternal(e.target.checked)}
                    className="h-3.5 w-3.5"
                  />
                  Mark as internal (staff only)
                </label>
              </div>
            </CardContent>
          </Card>

          {/* Fees */}
          <Card className="shadow-none">
            <CardHeader>
              <CardTitle className="text-lg flex items-center gap-2">
                <DollarSign className="h-4 w-4" />
                Fees
                {fees.length > 0 && (
                  <span className="ml-auto text-base font-semibold text-foreground">
                    Total: {formatCurrency(feeTotal)}
                  </span>
                )}
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              {fees.length === 0 ? (
                <p className="text-sm text-muted-foreground py-2 text-center">No fees added yet.</p>
              ) : (
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="border-b text-muted-foreground text-left">
                        <th className="pb-2 font-medium">Description</th>
                        <th className="pb-2 font-medium text-right">Qty</th>
                        <th className="pb-2 font-medium text-right">Unit Price</th>
                        <th className="pb-2 font-medium text-right">Total</th>
                        <th className="pb-2 font-medium text-right">Status</th>
                      </tr>
                    </thead>
                    <tbody>
                      {fees.map((fee) => (
                        <tr key={fee.id} className="border-b last:border-0">
                          <td className="py-2">{fee.description}</td>
                          <td className="py-2 text-right">{fee.quantity}</td>
                          <td className="py-2 text-right">{formatCurrency(fee.unit_price)}</td>
                          <td className="py-2 text-right font-medium">{formatCurrency(fee.total)}</td>
                          <td className="py-2 text-right">
                            <Badge variant="secondary" className="capitalize text-xs">
                              {fee.status}
                            </Badge>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                    {fees.length > 1 && (
                      <tfoot>
                        <tr className="border-t-2">
                          <td colSpan={3} className="pt-2 text-right font-medium text-muted-foreground">Grand Total</td>
                          <td className="pt-2 text-right font-bold">{formatCurrency(feeTotal)}</td>
                          <td />
                        </tr>
                      </tfoot>
                    )}
                  </table>
                </div>
              )}

              {/* Add fee form */}
              {showFeeForm ? (
                <div className="border rounded-lg p-3 space-y-2 bg-muted/30">
                  <p className="text-sm font-medium">Add Fee Line Item</p>
                  <Input
                    placeholder="Description"
                    value={feeDesc}
                    onChange={(e) => setFeeDesc(e.target.value)}
                    disabled={addingFee}
                  />
                  <div className="flex gap-2">
                    <Input
                      placeholder="Qty"
                      type="number"
                      min="0"
                      step="0.01"
                      value={feeQty}
                      onChange={(e) => setFeeQty(e.target.value)}
                      disabled={addingFee}
                      className="w-24"
                    />
                    <Input
                      placeholder="Unit price ($)"
                      type="number"
                      min="0"
                      step="0.01"
                      value={feePrice}
                      onChange={(e) => setFeePrice(e.target.value)}
                      disabled={addingFee}
                      className="flex-1"
                    />
                  </div>
                  <div className="flex gap-2">
                    <Button
                      onClick={handleAddFee}
                      disabled={addingFee || !feeDesc.trim() || !feePrice}
                      className="gap-1"
                    >
                      <Plus className="h-4 w-4" />
                      Add
                    </Button>
                    <Button
                      variant="outline"
                      onClick={() => { setShowFeeForm(false); setFeeDesc(""); setFeeQty("1"); setFeePrice(""); }}
                      disabled={addingFee}
                    >
                      Cancel
                    </Button>
                  </div>
                </div>
              ) : (
                <Button
                  variant="outline"
                  className="gap-1"
                  onClick={() => setShowFeeForm(true)}
                >
                  <Plus className="h-4 w-4" />
                  Add Fee
                </Button>
              )}

              {error && (
                <div className="flex items-center gap-2 text-sm text-destructive">
                  <AlertCircle className="h-4 w-4" />
                  {error}
                </div>
              )}
            </CardContent>
          </Card>

          {/* Response Letter */}
          <Card className="shadow-none">
            <CardHeader>
              <CardTitle className="text-lg flex items-center gap-2">
                <FileEdit className="h-4 w-4" />
                Response Letter
                {letter && (
                  <Badge
                    variant={letter.status === "approved" ? "default" : letter.status === "sent" ? "default" : "secondary"}
                    className="ml-auto capitalize text-xs"
                  >
                    {letter.status}
                  </Badge>
                )}
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              {generatingLetter ? (
                <div className="flex flex-col items-center justify-center py-8 gap-3">
                  <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
                  <p className="text-sm text-muted-foreground">Generating response letter...</p>
                </div>
              ) : letter ? (
                <>
                  {letter.status === "draft" && (
                    <div className="flex items-start gap-2 rounded-md border border-amber-300 bg-amber-50 dark:bg-amber-950/20 dark:border-amber-800 p-3">
                      <AlertCircle className="h-4 w-4 text-amber-600 mt-0.5 shrink-0" />
                      <p className="text-sm text-amber-800 dark:text-amber-200 font-medium">
                        AI-GENERATED DRAFT — Review before sending
                      </p>
                    </div>
                  )}
                  <RichTextEditor
                    content={letterContent}
                    onChange={setLetterContent}
                    disabled={letter.status === "sent"}
                  />
                  <div className="flex gap-2 flex-wrap">
                    <Button
                      onClick={handleSaveLetter}
                      disabled={savingLetter || letter.status === "sent"}
                      className="gap-1"
                    >
                      {savingLetter ? <Loader2 className="h-4 w-4 animate-spin" /> : <CheckCircle className="h-4 w-4" />}
                      Save Changes
                    </Button>
                    {letter.status === "draft" && (
                      <Button
                        variant="outline"
                        onClick={handleApproveLetter}
                        disabled={savingLetter}
                        className="gap-1"
                      >
                        <Eye className="h-4 w-4" />
                        Submit for Approval
                      </Button>
                    )}
                  </div>
                </>
              ) : (
                <div className="flex flex-col items-center justify-center py-6 gap-3">
                  <p className="text-sm text-muted-foreground">No response letter generated yet.</p>
                  {LETTER_ELIGIBLE_STATUSES.includes(req.status) && (
                    <Button
                      variant="outline"
                      className="gap-1"
                      disabled={generatingLetter}
                      onClick={handleGenerateLetter}
                    >
                      <FileEdit className="h-4 w-4" />
                      Generate Response Letter
                    </Button>
                  )}
                </div>
              )}
            </CardContent>
          </Card>
        </div>

        {/* Right column — workflow */}
        <div className="space-y-6">
          <Card className="shadow-none">
            <CardHeader>
              <CardTitle className="text-lg">Workflow</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              <p className="text-sm text-muted-foreground">
                Current status: <StatusBadge status={req.status} domain="request" />
              </p>
              {actions.map((a) => {
                const Icon = a.icon;
                return (
                  <Button
                    key={a.action}
                    variant={a.variant}
                    className="w-full justify-start gap-2"
                    disabled={actionLoading}
                    onClick={() => handleAction(a.action)}
                  >
                    <Icon className="h-4 w-4" />
                    {a.label}
                  </Button>
                );
              })}
              <Separator />
              <Link
                to="/search"
                className="inline-flex w-full items-center justify-start gap-2 rounded-lg border border-border bg-background px-2.5 h-8 text-sm font-medium hover:bg-muted hover:text-foreground transition-all"
              >
                <Search className="h-4 w-4" />
                Search &amp; Attach Documents
              </Link>
              {LETTER_ELIGIBLE_STATUSES.includes(req.status) && (
                <>
                  <Separator />
                  <Button
                    variant="outline"
                    className="w-full justify-start gap-2"
                    disabled={generatingLetter}
                    onClick={handleGenerateLetter}
                  >
                    {generatingLetter ? (
                      <Loader2 className="h-4 w-4 animate-spin" />
                    ) : (
                      <FileEdit className="h-4 w-4" />
                    )}
                    {generatingLetter ? "Generating..." : "Generate Response Letter"}
                  </Button>
                </>
              )}
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}
