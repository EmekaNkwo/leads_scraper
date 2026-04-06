"use client";

import { Header } from "@/components/header";
import { ScrapeForm } from "@/components/scrape-form";
import { JobTracker } from "@/components/job-tracker";
import { LeadsTable } from "@/components/leads-table";
import { ExportsList } from "@/components/exports-list";
import { JobsHistory } from "@/components/jobs-history";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
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
    formatBytes,
    formatDate,
  } = useExports();

  return (
    <div className="flex flex-1 flex-col">
      <Header />

      <main className="mx-auto flex w-full max-w-7xl flex-1 flex-col gap-6 p-6">
        <div className="grid gap-6 lg:grid-cols-[380px_minmax(0,1fr)]">
          {/* Left column: form + job history */}
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

          {/* Right column: status + results/exports tabs */}
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
      </main>
    </div>
  );
}
