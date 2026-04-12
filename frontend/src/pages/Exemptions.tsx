import { useState, useEffect } from "react";
import { apiFetch } from "@/lib/api";

interface Rule {
  id: string;
  state_code: string;
  category: string;
  rule_type: string;
  rule_definition: string;
  description: string | null;
  enabled: boolean;
}

interface Dashboard {
  total_flags: number;
  by_status: Record<string, number>;
  by_category: Record<string, number>;
  acceptance_rate: number;
  total_rules: number;
  active_rules: number;
}

interface Props { token: string; }

export default function Exemptions({ token }: Props) {
  const [rules, setRules] = useState<Rule[]>([]);
  const [dashboard, setDashboard] = useState<Dashboard | null>(null);
  const [error, setError] = useState("");
  const [showForm, setShowForm] = useState(false);
  const [stateCode, setStateCode] = useState("CO");
  const [category, setCategory] = useState("");
  const [ruleType, setRuleType] = useState("keyword");
  const [definition, setDefinition] = useState("");

  const load = () => {
    apiFetch<Rule[]>("/exemptions/rules/", { token }).then(setRules).catch((e: unknown) => setError(e instanceof Error ? e.message : String(e)));
    apiFetch<Dashboard>("/exemptions/dashboard", { token }).then(setDashboard).catch(() => {});
  };

  useEffect(load, [token]);

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      await apiFetch("/exemptions/rules/", {
        token, method: "POST",
        body: JSON.stringify({ state_code: stateCode, category, rule_type: ruleType, rule_definition: definition }),
      });
      setCategory(""); setDefinition(""); setShowForm(false); load();
    } catch (err: unknown) { setError(err instanceof Error ? err.message : String(err)); }
  };

  const toggleRule = async (id: string, enabled: boolean) => {
    try {
      await apiFetch(`/exemptions/rules/${id}`, { token, method: "PATCH", body: JSON.stringify({ enabled: !enabled }) });
      load();
    } catch (err: unknown) { setError(err instanceof Error ? err.message : String(err)); }
  };

  return (
    <div>
      <h2 className="text-lg font-semibold text-gray-900 mb-4">Exemption Detection</h2>
      {error && <p className="text-red-600 mb-4">{error}</p>}

      {dashboard && (
        <div className="grid grid-cols-2 md:grid-cols-5 gap-4 mb-6">
          <div className="bg-white p-4 rounded-lg border border-gray-200">
            <p className="text-sm text-gray-500">Total Flags</p>
            <p className="text-2xl font-semibold text-gray-900">{dashboard.total_flags}</p>
          </div>
          <div className="bg-white p-4 rounded-lg border border-gray-200">
            <p className="text-sm text-gray-500">Accepted</p>
            <p className="text-2xl font-semibold text-green-600">{dashboard.by_status.accepted || 0}</p>
          </div>
          <div className="bg-white p-4 rounded-lg border border-gray-200">
            <p className="text-sm text-gray-500">Rejected</p>
            <p className="text-2xl font-semibold text-red-600">{dashboard.by_status.rejected || 0}</p>
          </div>
          <div className="bg-white p-4 rounded-lg border border-gray-200">
            <p className="text-sm text-gray-500">Acceptance Rate</p>
            <p className="text-2xl font-semibold text-blue-600">{(dashboard.acceptance_rate * 100).toFixed(1)}%</p>
          </div>
          <div className="bg-white p-4 rounded-lg border border-gray-200">
            <p className="text-sm text-gray-500">Active Rules</p>
            <p className="text-2xl font-semibold text-gray-900">{dashboard.active_rules}/{dashboard.total_rules}</p>
          </div>
        </div>
      )}

      <div className="flex items-center justify-between mb-3">
        <h3 className="text-md font-semibold text-gray-900">Exemption Rules</h3>
        <button onClick={() => setShowForm(!showForm)} className="bg-blue-600 text-white px-4 py-2 rounded-md text-sm font-medium hover:bg-blue-700">
          {showForm ? "Cancel" : "Add Rule"}
        </button>
      </div>

      {showForm && (
        <form onSubmit={handleCreate} className="bg-white p-4 rounded-lg border border-gray-200 mb-4 space-y-3">
          <div className="grid grid-cols-3 gap-3">
            <div><label className="block text-sm font-medium text-gray-700 mb-1">State</label><input value={stateCode} onChange={(e) => setStateCode(e.target.value)} className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm" maxLength={2} required /></div>
            <div><label className="block text-sm font-medium text-gray-700 mb-1">Category</label><input value={category} onChange={(e) => setCategory(e.target.value)} placeholder="e.g. PII - SSN" className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm" required /></div>
            <div><label className="block text-sm font-medium text-gray-700 mb-1">Type</label>
              <select value={ruleType} onChange={(e) => setRuleType(e.target.value)} className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm">
                <option value="regex">Regex</option><option value="keyword">Keyword</option>
              </select>
            </div>
          </div>
          <div><label className="block text-sm font-medium text-gray-700 mb-1">Definition (regex pattern or comma-separated keywords)</label><input value={definition} onChange={(e) => setDefinition(e.target.value)} className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm" required /></div>
          <button type="submit" className="bg-blue-600 text-white px-4 py-2 rounded-md text-sm font-medium hover:bg-blue-700">Create Rule</button>
        </form>
      )}

      <div className="bg-white rounded-lg border border-gray-200 overflow-hidden">
        <table className="w-full text-sm">
          <thead><tr className="border-b border-gray-200 bg-gray-50">
            <th className="text-left px-4 py-3 font-medium text-gray-600">State</th>
            <th className="text-left px-4 py-3 font-medium text-gray-600">Category</th>
            <th className="text-left px-4 py-3 font-medium text-gray-600">Type</th>
            <th className="text-left px-4 py-3 font-medium text-gray-600">Definition</th>
            <th className="text-left px-4 py-3 font-medium text-gray-600">Status</th>
            <th className="text-left px-4 py-3 font-medium text-gray-600">Actions</th>
          </tr></thead>
          <tbody>{rules.map((r) => (
            <tr key={r.id} className="border-b border-gray-100">
              <td className="px-4 py-3 text-gray-600">{r.state_code}</td>
              <td className="px-4 py-3 text-gray-900">{r.category}</td>
              <td className="px-4 py-3"><span className="text-xs bg-gray-100 text-gray-600 px-2 py-0.5 rounded">{r.rule_type}</span></td>
              <td className="px-4 py-3 text-gray-600 max-w-xs truncate text-xs font-mono">{r.rule_definition}</td>
              <td className="px-4 py-3"><span className={`text-xs ${r.enabled ? "text-green-600" : "text-red-600"}`}>{r.enabled ? "Active" : "Disabled"}</span></td>
              <td className="px-4 py-3"><button onClick={() => toggleRule(r.id, r.enabled)} className="text-sm text-blue-600 hover:text-blue-800">{r.enabled ? "Disable" : "Enable"}</button></td>
            </tr>
          ))}</tbody>
        </table>
        {rules.length === 0 && <p className="text-center py-8 text-gray-400">No rules configured. Add rules or run the seed script.</p>}
      </div>
    </div>
  );
}
