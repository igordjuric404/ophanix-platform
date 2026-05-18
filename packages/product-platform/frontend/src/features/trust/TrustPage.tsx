import {
  BadgeCheck,
  FileSignature,
  Handshake,
  Link2,
  RefreshCw,
  ShieldCheck
} from "lucide-react";
import { useMemo, useState, type FormEvent, type ReactNode } from "react";

import {
  createTrustThreshold,
  issueTrustCard,
  patchTrustRule,
  patchTrustThreshold,
  recalculateTrust,
  revokeTrustCard,
  simulateTrustHandshake,
  useTrustCardDetail,
  useTrustCards,
  useTrustEvents,
  useTrustHandshakes,
  useTrustMutation,
  useTrustRules,
  useTrustScores,
  useTrustThresholds,
  verifyTrustCard,
  type TrustCard,
  type TrustCardVerification,
  type TrustEvent,
  type TrustHandshake,
  type TrustParams,
  type TrustRule,
  type TrustScore,
  type TrustThreshold
} from "../../api/trust";
import type { TenantContext } from "../../api/client";
import { useDetailDrawer } from "../../app/drawerContext";
import { PageHeader } from "../../components/layout/PageHeader";
import {
  ActionFeedback,
  actionErrorMessage,
  useActionFeedback
} from "../../components/shared/ActionFeedback";
import { EmptyState } from "../../components/shared/EmptyState";
import { QueryErrorSummary } from "../../components/shared/ErrorState";
import { StatusBadge } from "../../components/shared/StatusBadge";
import { TrustScore as TrustScoreValue } from "../../components/shared/TrustScore";
import { Badge } from "../../components/ui/badge";
import { Button } from "../../components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "../../components/ui/card";
import { Input } from "../../components/ui/input";
import { Label } from "../../components/ui/label";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow
} from "../../components/ui/table";
import { canRevokeTrustCard } from "../../lib/actionAvailability";
import { parseRequiredNumberField } from "../../lib/forms";
import { cn } from "../../lib/utils";

const dimensions = [
  "policy_compliance",
  "security_posture",
  "resource_efficiency",
  "output_quality",
  "collaboration_health"
];

const tiers = ["untrusted", "probationary", "standard", "trusted", "verified_partner"];

export function TrustPage() {
  const [eventFilters, setEventFilters] = useState<TrustParams>({});
  const [handshakeFilters, setHandshakeFilters] = useState<TrustParams>({});
  const [selectedCardId, setSelectedCardId] = useState<string | null>(null);
  const [selectedHandshakeId, setSelectedHandshakeId] = useState<string | null>(null);
  const [verification, setVerification] = useState<TrustCardVerification | null>(null);
  const [simulation, setSimulation] = useState<TrustHandshake | null>(null);
  const { feedback, runWithFeedback, setError } = useActionFeedback();

  const scoresQuery = useTrustScores();
  const eventsQuery = useTrustEvents(eventFilters);
  const rulesQuery = useTrustRules();
  const cardsQuery = useTrustCards();
  const thresholdsQuery = useTrustThresholds();
  const handshakesQuery = useTrustHandshakes(handshakeFilters);
  const mutation = useTrustMutation();

  const scores = scoresQuery.data ?? [];
  const events = eventsQuery.data ?? [];
  const rules = rulesQuery.data ?? [];
  const cards = cardsQuery.data ?? [];
  const thresholds = thresholdsQuery.data ?? [];
  const handshakes = handshakesQuery.data ?? [];
  const activeCardId = selectedCardId;
  const cardDetailQuery = useTrustCardDetail(activeCardId);
  const selectedCard =
    activeCardId
      ? cardDetailQuery.data ?? cards.find((card) => card.id === activeCardId) ?? null
      : null;
  const selectedHandshake =
    selectedHandshakeId
      ? handshakes.find((handshake) => handshake.id === selectedHandshakeId) ?? null
      : null;

  async function runTask(label: string, task: (tenantContext: TenantContext) => Promise<unknown>) {
    await runWithFeedback(() => mutation.mutateAsync(task), {
      errorMessage: `${label} failed`,
      successMessage: label
    });
  }

  return (
    <>
      <PageHeader title="Trust" description="Trust scores, cards, thresholds, and handshakes." />
      <div className="space-y-6 p-6">
        <ActionFeedback feedback={feedback} />
        <QueryErrorSummary
          items={[
            { error: scoresQuery.error, isError: scoresQuery.isError, label: "Trust scores", onRetry: () => void scoresQuery.refetch() },
            { error: eventsQuery.error, isError: eventsQuery.isError, label: "Trust events", onRetry: () => void eventsQuery.refetch() },
            { error: rulesQuery.error, isError: rulesQuery.isError, label: "Trust rules", onRetry: () => void rulesQuery.refetch() },
            { error: cardsQuery.error, isError: cardsQuery.isError, label: "Trust cards", onRetry: () => void cardsQuery.refetch() },
            { error: thresholdsQuery.error, isError: thresholdsQuery.isError, label: "Trust thresholds", onRetry: () => void thresholdsQuery.refetch() },
            { error: handshakesQuery.error, isError: handshakesQuery.isError, label: "Trust handshakes", onRetry: () => void handshakesQuery.refetch() },
            { error: cardDetailQuery.error, isError: cardDetailQuery.isError, label: "Trust card detail", onRetry: () => void cardDetailQuery.refetch() }
          ]}
        />
        <TrustSummary scores={scores} />
        <div className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_24rem]">
          <TrustLeaderboard
            isLoading={scoresQuery.isLoading}
            onRecalculate={(agentId) =>
              runTask("Trust recalculation queued", (tenantContext) =>
                recalculateTrust(agentId ? { agent_id: agentId } : {}, tenantContext)
              )
            }
            scores={scores}
          />
          <TrustRulesPanel
            onPatchRule={(rule) =>
              runTask(rule.enabled ? "Trust rule disabled" : "Trust rule enabled", (tenantContext) =>
                patchTrustRule(rule.id, { enabled: !rule.enabled }, tenantContext)
              )
            }
            rules={rules}
          />
        </div>
        <TrustEventsPanel events={events} filters={eventFilters} onFilter={setEventFilters} />
        <TrustCardsPanel
          cards={cards}
          selectedCard={selectedCard}
          verification={verification}
          onIssue={(payload) =>
            runTask("Trust card issued", async (tenantContext) => {
              const card = (await issueTrustCard(payload, tenantContext)) as TrustCard;
              setSelectedCardId(card.id);
              setVerification(null);
              return card;
            })
          }
          onRevoke={(cardId, payload) =>
            runTask("Trust card revoked", (tenantContext) =>
              revokeTrustCard(cardId, payload, tenantContext)
            )
          }
          onSelect={(cardId) => {
            setSelectedCardId(cardId);
            setVerification(null);
          }}
          onVerify={async (cardId) => {
            const result = await runWithFeedback<TrustCardVerification>(
              () =>
                mutation.mutateAsync((tenantContext) =>
                  verifyTrustCard(cardId, tenantContext)
                ) as Promise<TrustCardVerification>,
              {
                errorMessage: "Trust card verification failed",
                successMessage: (value) => (value.verified ? "Trust card verified" : "Trust card invalid")
              }
            );
            if (!result) {
              return;
            }
            setVerification(result);
          }}
        />
        <TrustThresholdsPanel
          onInvalidInput={(error) =>
            setError(actionErrorMessage(error, "Invalid trust threshold input"))
          }
          onCreate={(payload) =>
            runTask("Trust threshold created", (tenantContext) =>
              createTrustThreshold(payload, tenantContext)
            )
          }
          onPatch={(thresholdId, payload) =>
            runTask("Trust threshold updated", (tenantContext) =>
              patchTrustThreshold(thresholdId, payload, tenantContext)
            )
          }
          thresholds={thresholds}
        />
        <TrustHandshakesPanel
          filters={handshakeFilters}
          handshakes={handshakes}
          onFilter={setHandshakeFilters}
          onSelect={setSelectedHandshakeId}
          onSimulate={async (payload) => {
            const result = await runWithFeedback<TrustHandshake>(
              () =>
                mutation.mutateAsync((tenantContext) =>
                  simulateTrustHandshake(payload, tenantContext)
                ) as Promise<TrustHandshake>,
              {
                errorMessage: "Handshake simulation failed",
                successMessage: "Handshake simulated"
              }
            );
            if (!result) {
              return;
            }
            setSimulation(result);
            setSelectedHandshakeId(result.id);
          }}
          selectedHandshake={selectedHandshake}
          simulation={simulation}
        />
      </div>
    </>
  );
}

function TrustSummary({ scores }: { scores: TrustScore[] }) {
  const average = scores.length
    ? Math.round(scores.reduce((total, score) => total + Number(score.score ?? 0), 0) / scores.length)
    : 0;
  const trustedCount = scores.filter((score) =>
    ["trusted", "verified_partner"].includes(score.tier)
  ).length;
  const signalCount = scores.reduce((total, score) => total + countDimensionSignals(score), 0);

  return (
    <section className="grid gap-4 md:grid-cols-3" data-trust-summary>
      <MetricCard icon={<ShieldCheck className="h-4 w-4" />} label="Average Score" value={average || "n/a"} />
      <MetricCard icon={<BadgeCheck className="h-4 w-4" />} label="Trusted Agents" value={trustedCount} />
      <MetricCard icon={<RefreshCw className="h-4 w-4" />} label="Signals" value={signalCount} />
    </section>
  );
}

function TrustLeaderboard({
  isLoading,
  onRecalculate,
  scores
}: {
  isLoading: boolean;
  onRecalculate: (agentId?: string) => void;
  scores: TrustScore[];
}) {
  return (
    <Card data-trust-leaderboard>
      <CardHeader className="flex flex-row items-center justify-between gap-4">
        <CardTitle>Agent Trust Scores</CardTitle>
        <Button onClick={() => onRecalculate()}>
          <RefreshCw className="mr-2 h-4 w-4" />
          Recalculate
        </Button>
      </CardHeader>
      <CardContent>
        {scores.length === 0 ? (
          <EmptyState
            title={isLoading ? "Loading scores" : "No scores"}
            description={isLoading ? "Fetching trust scores." : "Run recalculation to populate scores."}
          />
        ) : (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Agent</TableHead>
                <TableHead>Score</TableHead>
                <TableHead>Tier</TableHead>
                <TableHead>Calculated</TableHead>
                <TableHead>Action</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {scores.map((score) => (
                <TableRow key={score.id} data-trust-score-row={score.agent_id}>
                  <TableCell>
                    <strong>{score.agent_name ?? score.agent_id}</strong>
                    <div className="text-xs text-muted-foreground">{score.agent_id}</div>
                  </TableCell>
                  <TableCell>
                    <div className="flex items-center gap-3">
                      <div className="h-2 w-24 overflow-hidden rounded-full bg-muted">
                        <div
                          className="h-full bg-primary"
                          style={{ width: `${scoreWidth(score.score)}%` }}
                        />
                      </div>
                      <TrustScoreValue score={score.score} />
                    </div>
                  </TableCell>
                  <TableCell>
                    <Badge tone={toneForTrustTier(score.tier)}>{score.tier}</Badge>
                  </TableCell>
                  <TableCell>{score.calculated_at}</TableCell>
                  <TableCell>
                    <Button onClick={() => onRecalculate(score.agent_id)} variant="outline">
                      Recalculate Agent
                    </Button>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </CardContent>
    </Card>
  );
}

function TrustRulesPanel({
  onPatchRule,
  rules
}: {
  onPatchRule: (rule: TrustRule) => void;
  rules: TrustRule[];
}) {
  return (
    <Card data-trust-rules>
      <CardHeader>
        <CardTitle>Signal Mapping</CardTitle>
      </CardHeader>
      <CardContent>
        {rules.length === 0 ? (
          <EmptyState title="No rules" description="Default trust rules will appear here." />
        ) : (
          <ul className="space-y-3">
            {rules.map((rule) => (
              <li
                className="flex items-center justify-between gap-3 rounded-md border p-3"
                data-trust-rule-row={rule.id}
                key={rule.id}
              >
                <div>
                  <div className="font-medium">{rule.event_type}</div>
                  <div className="text-sm text-muted-foreground">
                    {rule.dimension} {formatDelta(rule.delta)}
                  </div>
                </div>
                <Button onClick={() => onPatchRule(rule)} variant="outline">
                  {rule.enabled ? "Disable" : "Enable"}
                </Button>
              </li>
            ))}
          </ul>
        )}
      </CardContent>
    </Card>
  );
}

function TrustEventsPanel({
  events,
  filters,
  onFilter
}: {
  events: TrustEvent[];
  filters: TrustParams;
  onFilter: (params: TrustParams) => void;
}) {
  const { openAuditEvent } = useDetailDrawer();
  const trend = useMemo(() => [...events].reverse().slice(-8), [events]);

  function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    onFilter(trustEventParamsFromForm(event.currentTarget));
  }

  return (
    <div className="grid gap-6 xl:grid-cols-[22rem_minmax(0,1fr)]">
      <Card data-trust-score-trend>
        <CardHeader>
          <CardTitle>Score Movement</CardTitle>
        </CardHeader>
        <CardContent>
          {trend.length === 0 ? (
            <EmptyState title="No score movement" description="Trust events will appear here." />
          ) : (
            <ol className="space-y-3">
              {trend.map((event) => (
                <li className="flex items-center justify-between rounded-md border p-3" key={event.id}>
                  <span className="text-sm">{event.dimension}</span>
                  <strong>{formatDelta(event.delta)}</strong>
                  <span className="text-sm text-muted-foreground">{event.score_after}</span>
                </li>
              ))}
            </ol>
          )}
        </CardContent>
      </Card>
      <Card data-trust-score-events>
        <CardHeader>
          <CardTitle>Score Events</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <form className="grid gap-3 md:grid-cols-[1fr_1fr_auto]" onSubmit={onSubmit}>
            <Field compact label="Dimension" name="dimension">
              <select
                className="h-10 rounded-md border border-input bg-background px-3 text-sm"
                defaultValue={String(filters.dimension ?? "")}
                name="dimension"
              >
                <option value="">Any</option>
                {dimensions.map((dimension) => (
                  <option key={dimension} value={dimension}>
                    {dimension}
                  </option>
                ))}
              </select>
            </Field>
            <Field compact label="Agent" name="agent_id" defaultValue={String(filters.agent_id ?? "")} />
            <Button className="self-end" type="submit">
              Filter
            </Button>
          </form>
          {events.length === 0 ? (
            <EmptyState title="No events" description="Adjust filters or recalculate trust." />
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Agent</TableHead>
                  <TableHead>Dimension</TableHead>
                  <TableHead>Delta</TableHead>
                  <TableHead>Reason</TableHead>
                  <TableHead>Source</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {events.map((event) => (
                  <TableRow data-trust-event-row={event.id} key={event.id}>
                    <TableCell>
                      <strong>{event.agent_name ?? event.agent_id}</strong>
                      <div className="text-xs text-muted-foreground">{event.agent_id}</div>
                    </TableCell>
                    <TableCell>{event.dimension}</TableCell>
                    <TableCell>{formatDelta(event.delta)}</TableCell>
                    <TableCell>{event.reason}</TableCell>
                    <TableCell>
                      {event.source_event_id ? (
                        <Button
                          onClick={() => void openAuditEvent(event.source_event_id as string)}
                          variant="outline"
                        >
                          <Link2 className="mr-2 h-4 w-4" />
                          {event.source_event_id}
                        </Button>
                      ) : (
                        "none"
                      )}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>
    </div>
  );
}

function TrustCardsPanel({
  cards,
  onIssue,
  onRevoke,
  onSelect,
  onVerify,
  selectedCard,
  verification
}: {
  cards: TrustCard[];
  onIssue: (payload: Record<string, unknown>) => void;
  onRevoke: (cardId: string, payload: Record<string, unknown>) => void;
  onSelect: (cardId: string) => void;
  onVerify: (cardId: string) => void;
  selectedCard: TrustCard | null;
  verification: TrustCardVerification | null;
}) {
  function onIssueSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    onIssue(trustCardIssuePayloadFromForm(event.currentTarget));
  }

  return (
    <Card data-trust-card-inventory>
      <CardHeader className="flex flex-row items-center gap-3">
        <FileSignature className="h-5 w-5 text-muted-foreground" />
        <CardTitle>Card Inventory</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <form className="grid gap-3 md:grid-cols-[1fr_1fr_auto]" onSubmit={onIssueSubmit}>
          <Field compact label="Card Agent" name="agent_id" placeholder="agent_" />
          <Field
            compact
            defaultValue="ophanix-demo-issuer"
            label="Issuer"
            name="issuer"
          />
          <Button className="self-end" type="submit">
            Issue
          </Button>
        </form>
        <div className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_24rem]">
          <div className="overflow-x-auto">
            {cards.length === 0 ? (
              <EmptyState title="No trust cards" description="Issue a card for a registered agent." />
            ) : (
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Agent</TableHead>
                    <TableHead>Issuer</TableHead>
                    <TableHead>Status</TableHead>
                    <TableHead>Valid Until</TableHead>
                    <TableHead>Actions</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {cards.map((card) => (
                    <TableRow data-trust-card-row={card.id} key={card.id}>
                      <TableCell>
                        <strong>{cardName(card)}</strong>
                        <div className="text-xs text-muted-foreground">{card.agent_id}</div>
                      </TableCell>
                      <TableCell>{card.issuer}</TableCell>
                      <TableCell>
                        <StatusBadge status={card.status} />
                      </TableCell>
                      <TableCell>{card.valid_until}</TableCell>
                      <TableCell>
                        <div className="flex flex-wrap gap-2">
                          <Button onClick={() => onSelect(card.id)} variant="outline">
                            Open
                          </Button>
                          <Button onClick={() => onVerify(card.id)} variant="outline">
                            Verify
                          </Button>
                        </div>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            )}
          </div>
          <TrustCardDetail
            card={selectedCard}
            onRevoke={onRevoke}
            verification={verification?.trust_card_id === selectedCard?.id ? verification : null}
          />
        </div>
      </CardContent>
    </Card>
  );
}

function TrustCardDetail({
  card,
  onRevoke,
  verification
}: {
  card: TrustCard | null;
  onRevoke: (cardId: string, payload: Record<string, unknown>) => void;
  verification: TrustCardVerification | null;
}) {
  if (!card) {
    return <EmptyState title="No card selected" description="Issue or select a card." />;
  }
  const activeCard = card;
  const canRevoke = canRevokeTrustCard(activeCard);
  const payload = JSON.stringify(activeCard.card ?? {}, null, 2);
  function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!canRevoke) {
      return;
    }
    onRevoke(activeCard.id, trustCardRevokePayloadFromForm(event.currentTarget));
  }

  return (
    <section className="rounded-md border p-4" data-trust-card-detail={activeCard.id}>
      <div className="flex items-start justify-between gap-3">
        <div>
          <div className="text-sm text-muted-foreground">Card Detail</div>
          <h3 className="font-semibold">{cardName(activeCard)}</h3>
        </div>
        <StatusBadge status={activeCard.status} />
      </div>
      {activeCard.status === "revoked" ? (
        <div
          className="mt-3 feedback-warning px-3 py-2"
          data-trust-card-revoked
        >
          Revoked
        </div>
      ) : null}
      {verification ? (
        <div
          aria-live={verification.verified ? "polite" : "assertive"}
          className={cn(
            "mt-3 px-3 py-2",
            verification.verified ? "feedback-success" : "feedback-danger"
          )}
          data-trust-card-verification
          role={verification.verified ? "status" : "alert"}
        >
          {verification.verified ? "Verified" : "Invalid"} {verification.reason}
        </div>
      ) : null}
      <dl className="mt-4 grid gap-3 text-sm">
        <Metadata label="DID" value={stringFromCard(activeCard, "agent_did") ?? "unknown"} />
        <Metadata label="Score" value={String(trustScoreFromCard(activeCard))} />
        <Metadata label="Signature" value={activeCard.signature.slice(0, 18)} />
      </dl>
      <pre className="mt-4 max-h-48 overflow-auto rounded-md bg-muted p-3 text-xs">{payload}</pre>
      <form className="mt-4 grid gap-3 md:grid-cols-[1fr_auto]" onSubmit={onSubmit}>
        <Field compact disabled={!canRevoke} label="Revocation Reason" name="reason" />
        <Button className="self-end" disabled={!canRevoke} type="submit" variant="outline">
          Revoke
        </Button>
      </form>
    </section>
  );
}

function TrustThresholdsPanel({
  onInvalidInput,
  onCreate,
  onPatch,
  thresholds
}: {
  onInvalidInput: (error: unknown) => void;
  onCreate: (payload: Record<string, unknown>) => void;
  onPatch: (thresholdId: string, payload: Record<string, unknown>) => void;
  thresholds: TrustThreshold[];
}) {
  function onCreateSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    try {
      onCreate(trustThresholdPayloadFromForm(event.currentTarget));
    } catch (error) {
      onInvalidInput(error);
    }
  }

  return (
    <Card data-trust-thresholds>
      <CardHeader>
        <CardTitle>Protected Actions</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <form className="grid gap-3 md:grid-cols-6" onSubmit={onCreateSubmit}>
          <Field compact label="Threshold Type" name="threshold_type" placeholder="handoff" />
          <Field compact defaultValue="environment" label="Target Type" name="target_type" />
          <Field compact label="Target ID" name="target_id" placeholder="optional" />
          <Field compact defaultValue="700" label="Minimum Score" name="min_score" type="number" />
          <Field compact label="Required Tier" name="required_tier">
            <select className="h-10 rounded-md border border-input bg-background px-3 text-sm" name="required_tier">
              <option value="standard">standard</option>
              <option value="trusted">trusted</option>
              <option value="verified_partner">verified_partner</option>
              <option value="probationary">probationary</option>
              <option value="untrusted">untrusted</option>
            </select>
          </Field>
          <Button className="self-end" type="submit">
            Create
          </Button>
        </form>
        {thresholds.length === 0 ? (
          <EmptyState title="No thresholds" description="Seeded thresholds will appear here." />
        ) : (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Threshold</TableHead>
                <TableHead>Score</TableHead>
                <TableHead>Tier</TableHead>
                <TableHead>Status</TableHead>
                <TableHead>Edit</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {thresholds.map((threshold) => (
                <TableRow data-trust-threshold-row={threshold.id} key={threshold.id}>
                  <TableCell>
                    <strong>{threshold.threshold_type}</strong>
                    <div className="text-xs text-muted-foreground">
                      {threshold.target_type} {threshold.target_id ?? "default"}
                    </div>
                  </TableCell>
                  <TableCell>{threshold.min_score}</TableCell>
                  <TableCell>
                    <Badge tone={toneForTrustTier(threshold.required_tier)}>
                      {threshold.required_tier}
                    </Badge>
                  </TableCell>
                  <TableCell>{threshold.enabled ? "enabled" : "disabled"}</TableCell>
                  <TableCell>
                    <ThresholdPatchForm
                      onInvalidInput={onInvalidInput}
                      onPatch={onPatch}
                      threshold={threshold}
                    />
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </CardContent>
    </Card>
  );
}

function ThresholdPatchForm({
  onInvalidInput,
  onPatch,
  threshold
}: {
  onInvalidInput: (error: unknown) => void;
  onPatch: (thresholdId: string, payload: Record<string, unknown>) => void;
  threshold: TrustThreshold;
}) {
  function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    try {
      onPatch(threshold.id, trustThresholdPatchPayloadFromForm(event.currentTarget));
    } catch (error) {
      onInvalidInput(error);
    }
  }

  return (
    <form className="flex flex-wrap items-end gap-2" onSubmit={onSubmit}>
      <Input
        aria-label={`${threshold.id} score`}
        className="w-24"
        defaultValue={threshold.min_score}
        max={1000}
        min={0}
        name="min_score"
        type="number"
      />
      <select
        aria-label={`${threshold.id} tier`}
        className="h-10 rounded-md border border-input bg-background px-3 text-sm"
        defaultValue={threshold.required_tier}
        name="required_tier"
      >
        {tiers.map((tier) => (
          <option key={tier} value={tier}>
            {tier}
          </option>
        ))}
      </select>
      <Label className="flex h-10 items-center gap-2 text-sm">
        <input defaultChecked={threshold.enabled} name="enabled" type="checkbox" />
        Enabled
      </Label>
      <Button type="submit" variant="outline">
        Save
      </Button>
    </form>
  );
}

function TrustHandshakesPanel({
  filters,
  handshakes,
  onFilter,
  onSelect,
  onSimulate,
  selectedHandshake,
  simulation
}: {
  filters: TrustParams;
  handshakes: TrustHandshake[];
  onFilter: (params: TrustParams) => void;
  onSelect: (handshakeId: string) => void;
  onSimulate: (payload: Record<string, unknown>) => void;
  selectedHandshake: TrustHandshake | null;
  simulation: TrustHandshake | null;
}) {
  function onFilterSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    onFilter(trustHandshakeParamsFromForm(event.currentTarget));
  }

  function onSimulateSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    onSimulate(trustHandshakePayloadFromForm(event.currentTarget));
  }

  return (
    <Card data-trust-handshakes>
      <CardHeader className="flex flex-row items-center gap-3">
        <Handshake className="h-5 w-5 text-muted-foreground" />
        <CardTitle>Peer Attempts</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <form className="grid gap-3 md:grid-cols-[1fr_1fr_1fr_auto]" onSubmit={onFilterSubmit}>
          <Field compact defaultValue={String(filters.source_agent_id ?? "")} label="Source" name="source_agent_id" />
          <Field compact defaultValue={String(filters.target_agent_id ?? "")} label="Target" name="target_agent_id" />
          <Field compact label="Result" name="result">
            <select
              className="h-10 rounded-md border border-input bg-background px-3 text-sm"
              defaultValue={String(filters.result ?? "")}
              name="result"
            >
              <option value="">Any</option>
              <option value="allowed">allowed</option>
              <option value="denied">denied</option>
            </select>
          </Field>
          <Button className="self-end" type="submit">
            Filter
          </Button>
        </form>
        <form className="grid gap-3 lg:grid-cols-7" onSubmit={onSimulateSubmit}>
          <Field compact label="Sim Source" name="source_agent_id" placeholder="agent_source" />
          <Field compact label="Sim Target" name="target_agent_id" placeholder="agent_target" />
          <Field compact defaultValue="handoff" label="Type" name="threshold_type" />
          <Field compact label="Capabilities" name="required_capabilities" placeholder="claims:read,tools:run" />
          <Label className="flex h-10 items-center gap-2 self-end text-sm">
            <input name="require_trust_card" type="checkbox" />
            Card
          </Label>
          <Label className="flex h-10 items-center gap-2 self-end text-sm">
            <input name="require_active_credential" type="checkbox" />
            Credential
          </Label>
          <Button className="self-end" type="submit">
            Simulate
          </Button>
        </form>
        {simulation ? (
          <div
            className="feedback-success"
            data-trust-handshake-simulation
            role="status"
          >
            {simulation.result} {simulation.reason}
          </div>
        ) : null}
        <div className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_24rem]">
          {handshakes.length === 0 ? (
            <EmptyState title="No handshakes" description="Run a simulation to populate attempts." />
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Peers</TableHead>
                  <TableHead>Purpose</TableHead>
                  <TableHead>Result</TableHead>
                  <TableHead>Reason</TableHead>
                  <TableHead>Required</TableHead>
                  <TableHead>Detail</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {handshakes.map((handshake) => (
                  <TableRow data-trust-handshake-row={handshake.id} key={handshake.id}>
                    <TableCell>
                      <strong>{handshake.source_agent_id}</strong>
                      <div className="text-xs text-muted-foreground">to {handshake.target_agent_id}</div>
                    </TableCell>
                    <TableCell>{handshake.purpose}</TableCell>
                    <TableCell>
                      <StatusBadge status={handshake.result} />
                    </TableCell>
                    <TableCell>{handshake.reason}</TableCell>
                    <TableCell>{handshake.required_score}</TableCell>
                    <TableCell>
                      <Button onClick={() => onSelect(handshake.id)} variant="outline">
                        Details
                      </Button>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
          <HandshakeDetail handshake={selectedHandshake} />
        </div>
      </CardContent>
    </Card>
  );
}

function HandshakeDetail({ handshake }: { handshake: TrustHandshake | null }) {
  if (!handshake) {
    return <EmptyState title="No handshake selected" description="Select a handshake row." />;
  }
  return (
    <section className="rounded-md border p-4" data-handshake-detail={handshake.id}>
      <div className="flex items-start justify-between gap-3">
        <div>
          <div className="text-sm text-muted-foreground">Handshake Detail</div>
          <h3 className="font-semibold">
            {handshake.source_agent_id} to {handshake.target_agent_id}
          </h3>
        </div>
        <StatusBadge status={handshake.result} />
      </div>
      <dl className="mt-4 grid gap-3 text-sm">
        <Metadata label="Reason" value={handshake.reason} />
        <Metadata label="Required" value={`${handshake.required_score} ${handshake.required_tier}`} />
        <Metadata label="Source Score" value={String(handshake.source_score)} />
        <Metadata label="Target Score" value={String(handshake.target_score)} />
      </dl>
      <pre className="mt-4 max-h-48 overflow-auto rounded-md bg-muted p-3 text-xs">
        {JSON.stringify(handshake.metadata ?? {}, null, 2)}
      </pre>
    </section>
  );
}

function Field({
  children,
  className,
  compact,
  label,
  name,
  ...props
}: {
  children?: ReactNode;
  className?: string;
  compact?: boolean;
  label: string;
  name: string;
} & React.InputHTMLAttributes<HTMLInputElement>) {
  return (
    <Label className={cn("grid gap-1.5", className)}>
      <span className={cn("font-medium", compact && "text-xs text-muted-foreground")}>{label}</span>
      {children ?? <Input name={name} {...props} />}
    </Label>
  );
}

function MetricCard({ icon, label, value }: { icon: ReactNode; label: string; value: ReactNode }) {
  return (
    <Card>
      <CardContent className="flex items-center justify-between gap-3 p-5">
        <div>
          <div className="text-sm text-muted-foreground">{label}</div>
          <div className="mt-1 text-2xl font-semibold">{value}</div>
        </div>
        <div className="rounded-md border bg-muted p-2 text-muted-foreground">{icon}</div>
      </CardContent>
    </Card>
  );
}

function Metadata({ label, value }: { label: string; value: ReactNode }) {
  return (
    <div className="grid grid-cols-[8rem_minmax(0,1fr)] gap-3">
      <dt className="text-muted-foreground">{label}</dt>
      <dd className="break-words font-medium">{value}</dd>
    </div>
  );
}

export function trustEventParamsFromForm(form: HTMLFormElement) {
  const values = Object.fromEntries(new FormData(form));
  return compactParams({
    dimension: String(values.dimension ?? ""),
    agent_id: String(values.agent_id ?? "")
  });
}

export function trustHandshakeParamsFromForm(form: HTMLFormElement) {
  const values = Object.fromEntries(new FormData(form));
  return compactParams({
    source_agent_id: String(values.source_agent_id ?? ""),
    target_agent_id: String(values.target_agent_id ?? ""),
    result: String(values.result ?? "")
  });
}

export function trustCardIssuePayloadFromForm(form: HTMLFormElement) {
  const values = Object.fromEntries(new FormData(form));
  return {
    agent_id: String(values.agent_id ?? ""),
    issuer: String(values.issuer ?? "ophanix-demo-issuer")
  };
}

export function trustCardRevokePayloadFromForm(form: HTMLFormElement) {
  const values = Object.fromEntries(new FormData(form));
  return { reason: String(values.reason ?? "") };
}

export function trustThresholdPayloadFromForm(form: HTMLFormElement) {
  const values = Object.fromEntries(new FormData(form));
  return {
    threshold_type: String(values.threshold_type ?? ""),
    target_type: String(values.target_type ?? "environment"),
    target_id: blankToNull(values.target_id),
    min_score: parseRequiredNumberField(values.min_score, "Minimum Score", {
      emptyFallback: 0,
      integer: true,
      max: 1000,
      min: 0
    }),
    required_tier: String(values.required_tier ?? "standard"),
    enabled: true
  };
}

export function trustThresholdPatchPayloadFromForm(form: HTMLFormElement) {
  const values = Object.fromEntries(new FormData(form));
  return {
    min_score: parseRequiredNumberField(values.min_score, "Minimum Score", {
      emptyFallback: 0,
      integer: true,
      max: 1000,
      min: 0
    }),
    required_tier: String(values.required_tier ?? "standard"),
    enabled: Boolean(form.elements.namedItem("enabled") instanceof HTMLInputElement
      ? (form.elements.namedItem("enabled") as HTMLInputElement).checked
      : false)
  };
}

export function trustHandshakePayloadFromForm(form: HTMLFormElement) {
  const values = Object.fromEntries(new FormData(form));
  return {
    source_agent_id: String(values.source_agent_id ?? ""),
    target_agent_id: String(values.target_agent_id ?? ""),
    purpose: String(values.purpose ?? "handoff"),
    threshold_type: String(values.threshold_type ?? "handoff"),
    target_type: String(values.target_type ?? "environment"),
    target_id: blankToNull(values.target_id),
    required_capabilities: String(values.required_capabilities ?? "")
      .split(",")
      .map((capability) => capability.trim())
      .filter(Boolean),
    require_trust_card: isChecked(form, "require_trust_card"),
    require_active_credential: isChecked(form, "require_active_credential")
  };
}

function compactParams(params: TrustParams): TrustParams {
  return Object.fromEntries(
    Object.entries(params).filter(([, value]) => value !== undefined && value !== null && value !== "")
  );
}

function blankToNull(value: FormDataEntryValue | undefined) {
  const stripped = String(value ?? "").trim();
  return stripped || null;
}

function isChecked(form: HTMLFormElement, name: string) {
  const element = form.elements.namedItem(name);
  return element instanceof HTMLInputElement ? element.checked : false;
}

function countDimensionSignals(score: TrustScore): number {
  return Object.values(score.dimensions ?? {}).reduce<number>((total, dimension) => {
    if (dimension && typeof dimension === "object" && "signal_count" in dimension) {
      return total + Number((dimension as { signal_count?: unknown }).signal_count ?? 0);
    }
    return total;
  }, 0);
}

function scoreWidth(score: number) {
  return Math.max(0, Math.min(100, Math.round(Number(score ?? 0) / 10)));
}

function formatDelta(delta: number) {
  return `${delta > 0 ? "+" : ""}${delta}`;
}

function toneForTrustTier(tier: string): "default" | "success" | "warning" | "danger" | "muted" {
  if (tier === "verified_partner" || tier === "trusted") {
    return "success";
  }
  if (tier === "standard") {
    return "default";
  }
  if (tier === "probationary") {
    return "warning";
  }
  if (tier === "untrusted") {
    return "danger";
  }
  return "muted";
}

function cardName(card: TrustCard) {
  return stringFromCard(card, "name") ?? card.agent_id;
}

function stringFromCard(card: TrustCard, key: string) {
  const value = card.card?.[key];
  return typeof value === "string" ? value : null;
}

function trustScoreFromCard(card: TrustCard) {
  const metadata = card.card?.metadata;
  if (metadata && typeof metadata === "object" && "trust_score" in metadata) {
    return Number((metadata as { trust_score?: unknown }).trust_score ?? 0);
  }
  const score = card.card?.trust_score;
  return Math.round(Number(score ?? 0) * 1000);
}
