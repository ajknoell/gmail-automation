import axios from 'axios';

const api = axios.create({
  headers: {
    'Content-Type': 'application/json',
  },
});

// --- Workspace helpers ---

export const getActiveWorkspaceId = () => localStorage.getItem('activeWorkspaceId');

export const setActiveWorkspaceId = (id) => {
  localStorage.setItem('activeWorkspaceId', id);
  window.dispatchEvent(new CustomEvent('workspace-changed', { detail: { workspaceId: id } }));
};

// Attach X-Workspace-Id header to every request
api.interceptors.request.use((config) => {
  const wsId = getActiveWorkspaceId();
  if (wsId) {
    config.headers['X-Workspace-Id'] = wsId;
  }
  return config;
});

// Auth
export const getAuthStatus = () => api.get('/auth/status');
export const getSettings = () => api.get('/auth/settings');
export const saveSettings = (data) => api.post('/auth/settings', data);
export const disconnectGmail = () => api.post('/auth/gmail/disconnect');
export const getGmailConnectUrl = () => '/auth/gmail/connect';

// Gmail Accounts
export const getGmailAccounts = () => api.get('/auth/gmail/accounts');
export const disconnectGmailAccount = (id) => api.delete(`/auth/gmail/accounts/${id}`);
export const setDefaultGmailAccount = (id) => api.post(`/auth/gmail/accounts/${id}/default`);

// Templates
export const getTemplates = () => api.get('/api/templates');
export const getTemplate = (id) => api.get(`/api/templates/${id}`);
export const createTemplate = (data) => api.post('/api/templates', data);
export const updateTemplate = (id, data) => api.put(`/api/templates/${id}`, data);
export const deleteTemplate = (id) => api.delete(`/api/templates/${id}`);
export const previewTemplate = (id, sampleData) =>
  api.post(`/api/templates/${id}/preview`, { sample_data: sampleData });
export const generateTemplate = (data) => api.post('/api/templates/generate', data);
export const refineTemplate = (data) => api.post('/api/templates/refine', data);
export const getTemplateVariables = () => api.get('/api/templates/variables');

// Campaigns
export const getCampaigns = () => api.get('/api/campaigns');
export const getCampaign = (id) => api.get(`/api/campaigns/${id}`);
export const createCampaign = (data) => api.post('/api/campaigns', data);
export const updateCampaign = (id, data) => api.put(`/api/campaigns/${id}`, data);
export const deleteCampaign = (id) => api.delete(`/api/campaigns/${id}`);

// Campaign Recipients
export const uploadRecipients = (id, file, mapping) => {
  const formData = new FormData();
  formData.append('file', file);
  if (mapping) {
    formData.append('mapping', JSON.stringify(mapping));
  }
  return api.post(`/api/campaigns/${id}/upload`, formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  });
};
export const getRecipients = (id) => api.get(`/api/campaigns/${id}/recipients`);
export const clearRecipients = (id) => api.delete(`/api/campaigns/${id}/recipients`);
export const deleteRecipient = (campaignId, recipientId) => api.delete(`/api/campaigns/${campaignId}/recipients/${recipientId}`);
export const moveRecipients = (campaignId, recipientIds, targetCampaignId, newCampaignName) =>
  api.post(`/api/campaigns/${campaignId}/recipients/move`, {
    recipient_ids: recipientIds,
    target_campaign_id: targetCampaignId || undefined,
    new_campaign_name: newCampaignName || undefined,
  });
export const generatePreview = (id, batchSize, { regenerate } = {}) => {
  const body = {};
  if (batchSize != null) body.batch_size = batchSize;
  if (regenerate) body.regenerate = true;
  return api.post(`/api/campaigns/${id}/generate-preview`, body);
};
export const approveRecipients = (id, recipientIds) =>
  api.post(`/api/campaigns/${id}/approve`, { recipient_ids: recipientIds });
export const sendIndividual = (campaignId, recipientId) =>
  api.post(`/api/campaigns/${campaignId}/send-individual`, { recipient_id: recipientId });
export const updateRecipient = (campaignId, recipientId, data) =>
  api.put(`/api/campaigns/${campaignId}/recipients/${recipientId}`, data);
export const regenerateRecipientPreview = (campaignId, recipientId) =>
  api.post(`/api/campaigns/${campaignId}/recipients/${recipientId}/regenerate`);

// Add Recipient to Running Campaign
export const addRecipientToCampaign = (campaignId, data) =>
  api.post(`/api/campaigns/${campaignId}/add-recipient`, data);
export const addRecipientsBulkToCampaign = (campaignId, file, mapping) => {
  const formData = new FormData();
  formData.append('file', file);
  if (mapping) {
    formData.append('mapping', JSON.stringify(mapping));
  }
  return api.post(`/api/campaigns/${campaignId}/add-recipients-bulk`, formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  });
};
export const checkAddRecipientStatus = (campaignId) =>
  api.get(`/api/campaigns/${campaignId}/add-recipient-status`);

// Campaign Steps
export const getSteps = (campaignId) => api.get(`/api/campaigns/${campaignId}/steps`);
export const createStep = (campaignId, data) => api.post(`/api/campaigns/${campaignId}/steps`, data);
export const updateStep = (campaignId, stepId, data) => api.put(`/api/campaigns/${campaignId}/steps/${stepId}`, data);
export const deleteStep = (campaignId, stepId) => api.delete(`/api/campaigns/${campaignId}/steps/${stepId}`);
export const getStepRecipients = (campaignId, stepId) => api.get(`/api/campaigns/${campaignId}/steps/${stepId}/recipients`);
export const generateStepPreview = (campaignId, stepId, batchSize) =>
  api.post(`/api/campaigns/${campaignId}/steps/${stepId}/generate-preview`, batchSize != null ? { batch_size: batchSize } : {});
export const approveStepRecipients = (campaignId, stepId, recipientIds) =>
  api.post(`/api/campaigns/${campaignId}/steps/${stepId}/approve`, recipientIds ? { recipient_ids: recipientIds } : {});
export const updateStepRecipient = (campaignId, stepId, srId, data) =>
  api.put(`/api/campaigns/${campaignId}/steps/${stepId}/recipients/${srId}`, data);
export const regenerateStepRecipient = (campaignId, stepId, srId) =>
  api.post(`/api/campaigns/${campaignId}/steps/${stepId}/recipients/${srId}/regenerate`);
export const startStep = (campaignId, stepId) => api.post(`/api/campaigns/${campaignId}/steps/${stepId}/start`);

// Campaign Actions
export const startCampaign = (id, data) => api.post(`/api/campaigns/${id}/start`, data);
export const pauseCampaign = (id) => api.post(`/api/campaigns/${id}/pause`);
export const resumeCampaign = (id) => api.post(`/api/campaigns/${id}/resume`);
export const cancelCampaign = (id) => api.post(`/api/campaigns/${id}/cancel`);
export const exportCampaign = (id) => `/api/campaigns/${id}/export`;

// SSE Progress
export const getCampaignProgressUrl = (id) => `/api/campaigns/${id}/progress`;
export const getGenerationProgressUrl = (id) => `/api/campaigns/${id}/generation-progress`;
export const cancelGeneration = (id) => api.post(`/api/campaigns/${id}/cancel-generation`);

// Sample CSV
export const getSampleCsvUrl = () => '/api/campaigns/sample-csv';

// Quick Send (one-off emails)
export const generateQuickEmail = (data) => api.post('/api/quick-send/generate', data);
export const sendQuickEmail = (data) => api.post('/api/quick-send/send', data);

// Tracking
export const getCampaignTracking = (id) => api.get(`/api/campaigns/${id}/tracking`);
export const getQuickSendHistory = () => api.get('/api/quick-send/history');
export const triggerReplyCheck = () => api.post('/api/tracking/check-replies');

// Clay Integration
export const getClaySettings = () => api.get('/api/clay/settings');
export const saveClaySettings = (data) => api.post('/api/clay/settings', data);
export const getClayWebhookUrl = () => api.get('/api/clay/webhook-url');
export const exportToClay = (campaignId) => api.post(`/api/clay/export/${campaignId}`);

// Contacts Directory
export const getContacts = (params) => api.get('/api/contacts', { params });
export const getContact = (id) => api.get(`/api/contacts/${id}`);
export const updateContact = (id, data) => api.put(`/api/contacts/${id}`, data);
export const deleteContact = (id) => api.delete(`/api/contacts/${id}`);
export const getContactStatuses = () => api.get('/api/contacts/statuses');

// Tags
export const getTags = () => api.get('/api/contacts/tags');
export const createTag = (data) => api.post('/api/contacts/tags', data);
export const deleteTag = (id) => api.delete(`/api/contacts/tags/${id}`);
export const addTagToContact = (contactId, data) => api.post(`/api/contacts/${contactId}/tags`, data);
export const removeTagFromContact = (contactId, tagId) => api.delete(`/api/contacts/${contactId}/tags/${tagId}`);

// Reply Hub
export const getReplies = (params) => api.get('/api/replies', { params });
export const getReply = (id) => api.get(`/api/replies/${id}`);
export const classifyReply = (id) => api.post(`/api/replies/${id}/classify`);
export const generateReplyResponse = (id, data) => api.post(`/api/replies/${id}/generate-response`, data);
export const sendReplyResponse = (id, data) => api.post(`/api/replies/${id}/send-response`, data);
export const dismissReply = (id) => api.post(`/api/replies/${id}/dismiss`);
export const getReplyStats = () => api.get('/api/replies/stats');
export const getCalendarStatus = () => api.get('/api/replies/calendar-status');
export const setReplyFollowUp = (replyId, data) => api.post(`/api/replies/${replyId}/set-followup`, data);

// Follow-ups
export const getFollowUps = () => api.get('/api/contacts/follow-ups');
export const generateFollowUp = (contactId) => api.post(`/api/contacts/${contactId}/generate-followup`);

// Cold Calls
export const getColdCalls = (params) => api.get('/api/cold-calls', { params });
export const createColdCall = (data) => api.post('/api/cold-calls', data);
export const updateColdCall = (id, data) => api.put(`/api/cold-calls/${id}`, data);
export const deleteColdCall = (id) => api.delete(`/api/cold-calls/${id}`);
export const getColdCallOutcomes = () => api.get('/api/cold-calls/outcomes');

// Workspaces
export const getWorkspaces = () => api.get('/api/workspaces/');
export const createWorkspace = (data) => api.post('/api/workspaces/', data);
export const updateWorkspace = (id, data) => api.put(`/api/workspaces/${id}`, data);
export const deleteWorkspace = (id) => api.delete(`/api/workspaces/${id}`);

// Features
export const getEnabledFeatures = () => api.get('/api/features/enabled');
export const getAllFeatures = () => api.get('/api/features');
export const updateFeatureVisibility = (featureName, enabled) =>
  api.put(`/api/features/${featureName}/visibility`, { enabled });

// Insights / Feedback Loop
export const getInsights = () => api.get('/api/insights');
export const triggerAnalysis = () => api.post('/api/insights/analyze');
export const getEmailScores = () => api.get('/api/insights/email-scores');

// Attachments
export const uploadAttachments = (files) => {
  const formData = new FormData();
  files.forEach((f) => formData.append('files', f));
  return api.post('/api/attachments/upload', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  });
};
export const deleteAttachment = (id) => api.delete(`/api/attachments/${id}`);

// Listing Monitor
export const getMonitoredSites = () => api.get('/api/listings/sites');
export const createMonitoredSite = (data) => api.post('/api/listings/sites', data);
export const updateMonitoredSite = (id, data) => api.put(`/api/listings/sites/${id}`, data);
export const deleteMonitoredSite = (id) => api.delete(`/api/listings/sites/${id}`);
export const checkSiteNow = (id) => api.post(`/api/listings/sites/${id}/check`);
export const checkAllSitesNow = () => api.post('/api/listings/check-all');
export const getListings = (params) => api.get('/api/listings', { params });
export const getListingStats = () => api.get('/api/listings/stats');
export const getListingFilterOptions = () => api.get('/api/listings/filter-options');
export const markListingSeen = (id) => api.post(`/api/listings/${id}/mark-seen`);
export const markAllListingsSeen = (siteId) => api.post(`/api/listings/mark-all-seen${siteId ? `?site_id=${siteId}` : ''}`);
export const updateListingNotes = (id, notes) => api.put(`/api/listings/${id}/notes`, { notes });
export const fetchSiteInfo = (url) => api.post('/api/listings/site-info', { url });
export const getDealCriteria = () => api.get('/api/listings/deal-criteria');
export const updateDealCriteria = (data) => api.put('/api/listings/deal-criteria', data);
export const getStandardCategories = () => api.get('/api/listings/categories/standard');
export const normalizeCategory = (category) => api.post('/api/listings/categories/normalize', { category });
export const quickAddListing = (data) => api.post('/api/listings/quick-add', data);
export const parseEmailPreview = (data) => api.post('/api/listings/parse-email', data);
export const ingestEmailListing = (data) => api.post('/api/listings/ingest-email', data);
export const scanEmailAlerts = (data) => api.post('/api/listings/scan-email-alerts', data);

// Map Explorer
export const getMapApiKey = () => api.get('/api/map-explorer/maps-js-key');
export const geocodeAddress = (address) =>
  api.get('/api/map-explorer/geocode', { params: { address } });
export const searchNearbyPlaces = (data) =>
  api.post('/api/map-explorer/search', data);
export const textSearchPlaces = (data) =>
  api.post('/api/map-explorer/text-search', data);
export const getMapSources = () => api.get('/api/map-explorer/sources');
export const addPlaceToOutreach = (data) =>
  api.post('/api/map-explorer/add-to-outreach', data);
export const addPlaceToPipeline = (data) =>
  api.post('/api/map-explorer/add-to-pipeline', data);
export const bulkAddToPipeline = (businesses) =>
  api.post('/api/map-explorer/bulk-add-to-pipeline', { businesses });

// --- Pipeline ---
export const getPipelineLeads = (params) => api.get('/api/pipeline/', { params });
export const getPipelineStats = () => api.get('/api/pipeline/stats');
export const getPipelineLead = (id) => api.get(`/api/pipeline/${id}`);
export const createPipelineLead = (data) => api.post('/api/pipeline/', data);
export const updatePipelineLead = (id, data) => api.put(`/api/pipeline/${id}`, data);
export const deletePipelineLead = (id) => api.delete(`/api/pipeline/${id}`);
export const enrichPipelineLead = (id) => api.post(`/api/pipeline/${id}/enrich`);
export const bulkEnrichLeads = (leadIds) => api.post('/api/pipeline/bulk-enrich', { lead_ids: leadIds });
export const approvePipelineLead = (id, data) => api.post(`/api/pipeline/${id}/approve`, data);
export const bulkApproveLeads = (data) => api.post('/api/pipeline/bulk-approve', data);
export const bulkRejectLeads = (leadIds) => api.post('/api/pipeline/bulk-reject', { lead_ids: leadIds });

// --- Discovery (Phase 1) ---
export const getDiscoveryCriteria = () => api.get('/api/discovery/criteria');
export const createDiscoveryCriteria = (data) => api.post('/api/discovery/criteria', data);
export const updateDiscoveryCriteria = (id, data) => api.put(`/api/discovery/criteria/${id}`, data);
export const deleteDiscoveryCriteria = (id) => api.delete(`/api/discovery/criteria/${id}`);
export const triggerDiscoveryScan = (data) => api.post('/api/discovery/scan-now', data || {});
export const getProspects = (params) => api.get('/api/discovery/prospects', { params });
export const qualifyProspect = (id, data) => api.post(`/api/discovery/prospects/${id}/qualify`, data);
export const addProspectToCampaign = (id, data) => api.post(`/api/discovery/prospects/${id}/add-to-campaign`, data);
export const bulkAddProspects = (data) => api.post('/api/discovery/prospects/bulk-add', data);
export const dismissProspect = (id) => api.delete(`/api/discovery/prospects/${id}`);
export const getDiscoveryStats = () => api.get('/api/discovery/stats');

// --- Daily Brief (Phase 4) ---
export const getDailyBrief = (date) => api.get('/api/brief', date ? { params: { date } } : {});

// --- Reply Autopilot (Phase 3) ---
export const getAutopilotConfig = () => api.get('/api/replies/autopilot-config');
export const updateAutopilotConfig = (data) => api.put('/api/replies/autopilot-config', data);
export const getAutopilotStats = () => api.get('/api/replies/autopilot-stats');

// --- Triggers (Phase 5) ---
export const getTriggers = (params) => api.get('/api/triggers', { params });
export const createTriggerOutreach = (id, data) => api.post(`/api/triggers/${id}/create-outreach`, data || {});
export const dismissTrigger = (id) => api.put(`/api/triggers/${id}/dismiss`);
export const getTriggerStats = () => api.get('/api/triggers/stats');
export const getTriggerConfig = () => api.get('/api/triggers/config');
export const updateTriggerConfig = (data) => api.put('/api/triggers/config', data);
export const triggerCheckNow = () => api.post('/api/triggers/check-now');

// --- Signals ---
export const getSignals = (params) => api.get('/api/signals', { params });
export const getSignalStats = () => api.get('/api/signals/stats');
export const dismissSignal = (id) => api.post(`/api/signals/${id}/dismiss`);
export const createSignalOutreach = (id) => api.post(`/api/signals/${id}/create-outreach`);
export const getSignalSources = () => api.get('/api/signals/sources');
export const createSignalSource = (data) => api.post('/api/signals/sources', data);
export const updateSignalSource = (id, data) => api.put(`/api/signals/sources/${id}`, data);
export const signalCollectNow = () => api.post('/api/signals/collect-now');

// --- Business Profile ---
export const getBusinessProfile = () => api.get('/api/profile');
export const updateBusinessProfile = (data) => api.put('/api/profile', data);

// --- Opportunities ---
export const getOpportunityFeed = (params) => api.get('/api/opportunities/feed', { params });

// --- Agents ---
export const getAgentTasks = (params) => api.get('/api/agents/tasks', { params });
export const getAgentTask = (id) => api.get(`/api/agents/tasks/${id}`);
export const startProspectResearch = (leadId) => api.post('/api/agents/research', { lead_id: leadId });
export const startLeadDiscovery = (data) => api.post('/api/agents/discover', data);
export const startCompetitiveIntel = (data) => api.post('/api/agents/competitive-intel', data);
export const cancelAgentTask = (id) => api.post(`/api/agents/tasks/${id}/cancel`);
export const getAgentStats = () => api.get('/api/agents/stats');

export default api;
