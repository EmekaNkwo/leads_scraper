"use client";

import { AgentInsights } from "@/components/agent-insights";
import { AgentRunForm } from "@/components/agent-run-form";
import { AgentRunTracker } from "@/components/agent-run-tracker";
import { AgentRunsHistory } from "@/components/agent-runs-history";
import { Header } from "@/components/header";
import { ScrapeForm } from "@/components/scrape-form";
import { JobTracker } from "@/components/job-tracker";
import { LeadsTable } from "@/components/leads-table";
import { ExportsList } from "@/components/exports-list";
import { JobsHistory } from "@/components/jobs-history";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { useAgentRun } from "@/hooks/use-agent-run";
import { useScraper } from "@/hooks/use-scraper";
import { useExports } from "@/hooks/use-exports";

export default function Dashboard() {
  const {
    form,
    queriesText,
    updateForm,
    setQueries,
    submit,
    isSubmitting,
    activeJob,
    activeJobId,
    isRunning,
    elapsed,
    formatElapsed,
    jobs,
    viewJob,
    cancelJob,
    cancellingJobId,
  } = useScraper();

  const {
    exports,
    isLoading: exportsLoading,
    refetch: refetchExports,
    downloadFile,
    downloadJobCsv,
    downloadAgentRunCsv,
    formatBytes,
    formatDate,
  } = useExports();

  const {
    form: agentForm,
    updateForm: updateAgentForm,
    submit: submitAgentRun,
    isSubmitting: isSubmittingAgentRun,
    errorMessage: agentErrorMessage,
    activeRun,
    activeRunId,
    isRunning: isAgentRunning,
    elapsed: agentElapsed,
    formatElapsed: formatAgentElapsed,
    runs: agentRuns,
    viewRun,
    cancelRun,
    cancellingRunId,
  } = useAgentRun();

  return (
    <div className="flex flex-1 flex-col">
      <Header />

      <main className="mx-auto flex w-full max-w-7xl flex-1 flex-col gap-6 p-6">
        <Tabs defaultValue="scraper" className="flex flex-1 flex-col gap-6">
          <TabsList className="w-fit">
            <TabsTrigger value="scraper">
              Scraper
              {activeJob && activeJob.leads.length > 0 && (
                <span className="ml-1.5 rounded-full bg-primary px-1.5 py-0.5 text-[10px] font-semibold text-primary-foreground">
                  {activeJob.leads.length}
                </span>
              )}
            </TabsTrigger>
            <TabsTrigger value="agent">
              Agent
              {activeRun?.analysis?.top_leads.length ? (
                <span className="ml-1.5 rounded-full bg-primary px-1.5 py-0.5 text-[10px] font-semibold text-primary-foreground">
                  {activeRun.analysis.top_leads.length}
                </span>
              ) : null}
            </TabsTrigger>
          </TabsList>

          <TabsContent value="scraper" className="mt-0">
            <div className="grid gap-6 lg:grid-cols-[380px_minmax(0,1fr)]">
              <div className="flex min-w-0 flex-col gap-6">
                <ScrapeForm
                  form={form}
                  queriesText={queriesText}
                  isSubmitting={isSubmitting}
                  isRunning={isRunning}
                  onUpdateForm={updateForm}
                  onSetQueries={setQueries}
                  onSubmit={submit}
                />
                <JobsHistory
                  jobs={jobs}
                  activeJobId={activeJobId}
                  onViewJob={viewJob}
                  onCancelJob={cancelJob}
                  cancellingJobId={cancellingJobId}
                />
              </div>

              <div className="flex min-w-0 flex-col gap-6">
                <JobTracker
                  job={activeJob}
                  onDownloadCsv={downloadJobCsv}
                  isRunning={isRunning}
                  elapsed={elapsed}
                  formatElapsed={formatElapsed}
                />

                <Tabs defaultValue="results">
                  <TabsList>
                    <TabsTrigger value="results">
                      Results
                      {activeJob && activeJob.leads.length > 0 && (
                        <span className="ml-1.5 rounded-full bg-primary px-1.5 py-0.5 text-[10px] font-semibold text-primary-foreground">
                          {activeJob.leads.length}
                        </span>
                      )}
                    </TabsTrigger>
                    <TabsTrigger value="exports">
                      Exports
                      {exports.length > 0 && (
                        <span className="ml-1.5 rounded-full bg-muted px-1.5 py-0.5 text-[10px] font-semibold">
                          {exports.length}
                        </span>
                      )}
                    </TabsTrigger>
                  </TabsList>

                  <TabsContent value="results" className="mt-4">
                    <LeadsTable
                      leads={activeJob?.leads ?? []}
                      jobId={activeJobId}
                      onDownloadCsv={downloadJobCsv}
                    />
                  </TabsContent>

                  <TabsContent value="exports" className="mt-4">
                    <ExportsList
                      exports={exports}
                      isLoading={exportsLoading}
                      onRefresh={refetchExports}
                      onDownload={downloadFile}
                      formatBytes={formatBytes}
                      formatDate={formatDate}
                    />
                  </TabsContent>
                </Tabs>
              </div>
            </div>
          </TabsContent>

          <TabsContent value="agent" className="mt-0">
            <div className="grid gap-6 lg:grid-cols-[380px_minmax(0,1fr)]">
              <div className="flex min-w-0 flex-col gap-6">
                <AgentRunForm
                  form={agentForm}
                  isSubmitting={isSubmittingAgentRun}
                  isRunning={isAgentRunning}
                  errorMessage={agentErrorMessage}
                  onUpdateForm={updateAgentForm}
                  onSubmit={submitAgentRun}
                />
                <AgentRunsHistory
                  runs={agentRuns}
                  activeRunId={activeRunId}
                  onViewRun={viewRun}
                  onCancelRun={cancelRun}
                  cancellingRunId={cancellingRunId}
                />
              </div>

              <div className="flex min-w-0 flex-col gap-6">
                <AgentRunTracker
                  run={activeRun}
                  isRunning={isAgentRunning}
                  elapsed={agentElapsed}
                  formatElapsed={formatAgentElapsed}
                  onDownloadCsv={downloadAgentRunCsv}
                />
                <AgentInsights run={activeRun} />
              </div>
            </div>
          </TabsContent>
        </Tabs>
      </main>
    </div>
  );
}
