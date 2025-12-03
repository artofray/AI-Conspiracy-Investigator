import React, { useState, useEffect, useCallback, useRef } from 'react';
import { Search, Bell, TrendingUp, Users, FileText, Globe, Radio, Eye, EyeOff, Plus, X, Play, Pause, Volume2, VolumeX, Filter, Download, Share2, AlertTriangle, CheckCircle, Clock, Zap, Target, Network, Calendar, MessageSquare, Youtube, Twitter, Newspaper, Hash, AtSign, ChevronRight, ChevronDown, Settings, Moon, Sun, Mic, MicOff, RefreshCw, ExternalLink, Heart, Repeat, BarChart3, PieChart, Activity, Layers, BookOpen, Shield, Sparkles, Brain, Link2, MapPin } from 'lucide-react';

// ============ SHADOW INVESTIGATION PLATFORM ============
// Open Source Intelligence Tool for Truth Seekers
// Real-time social monitoring + FOIA document analysis

export default function ShadowPlatform() {
  // ===== STATE =====
  const [darkMode, setDarkMode] = useState(true);
  const [currentView, setCurrentView] = useState('dashboard');
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  
  // Search & Voice
  const [searchQuery, setSearchQuery] = useState('');
  const [isListening, setIsListening] = useState(false);
  const [voiceEnabled, setVoiceEnabled] = useState(true);
  
  // Real-time data
  const [posts, setPosts] = useState([]);
  const [alerts, setAlerts] = useState([]);
  const [monitorQueries, setMonitorQueries] = useState([]);
  const [stats, setStats] = useState({});
  const [isMonitoring, setIsMonitoring] = useState(false);
  const [wsConnected, setWsConnected] = useState(false);
  
  // UI state
  const [showAddQuery, setShowAddQuery] = useState(false);
  const [selectedPost, setSelectedPost] = useState(null);
  const [notifications, setNotifications] = useState([]);
  const [filterPlatform, setFilterPlatform] = useState('all');
  
  // WebSocket ref
  const wsRef = useRef(null);
  
  // ===== MOCK DATA FOR DEMO =====
  const mockPosts = [
    {
      id: '1',
      platform: 'twitter',
      author: 'investigator_x',
      content: 'Just discovered a connection between the offshore accounts mentioned in the FOIA release and the shell company network. Thread incoming... 🧵',
      url: 'https://twitter.com/investigator_x/status/123',
      created_at: new Date(Date.now() - 300000).toISOString(),
      likes: 1247,
      shares: 892,
      comments: 156,
      matched_queries: ['offshore accounts', 'shell company'],
      sentiment: 'neutral'
    },
    {
      id: '2', 
      platform: 'reddit',
      author: 'deep_dig_42',
      title: '[MEGATHREAD] Analysis of newly released documents',
      content: 'I\'ve been going through the latest document dump and found several previously unknown connections...',
      url: 'https://reddit.com/r/conspiracy/comments/abc123',
      created_at: new Date(Date.now() - 600000).toISOString(),
      likes: 3421,
      comments: 567,
      matched_queries: ['document dump'],
      sentiment: 'positive'
    },
    {
      id: '3',
      platform: 'youtube',
      author: 'Truth Seekers Network',
      title: 'BREAKING: New Evidence Exposed in Latest FOIA Release',
      content: 'In this video we analyze the most significant findings from the recent Freedom of Information Act releases...',
      url: 'https://youtube.com/watch?v=xyz789',
      created_at: new Date(Date.now() - 900000).toISOString(),
      views: 45678,
      likes: 4521,
      comments: 892,
      matched_queries: ['FOIA release'],
      sentiment: 'neutral'
    },
    {
      id: '4',
      platform: 'news',
      author: 'The Independent',
      title: 'Newly declassified documents reveal extent of surveillance program',
      content: 'Documents obtained through FOIA requests show the program was far more extensive than previously known...',
      url: 'https://independent.co.uk/news/article123',
      created_at: new Date(Date.now() - 1200000).toISOString(),
      matched_queries: ['declassified', 'surveillance'],
      sentiment: 'negative'
    },
    {
      id: '5',
      platform: 'bluesky',
      author: 'osint.expert',
      content: 'Cross-referencing the flight logs with the financial records paints a very interesting picture. More to come.',
      url: 'https://bsky.app/profile/osint.expert/post/123',
      created_at: new Date(Date.now() - 1500000).toISOString(),
      likes: 234,
      shares: 89,
      matched_queries: ['flight logs', 'financial records'],
      sentiment: 'neutral'
    }
  ];

  const mockQueries = [
    { id: '1', name: 'Epstein Network', query: 'epstein OR "maxwell" OR "little st james"', platforms: ['twitter', 'reddit', 'news'], enabled: true },
    { id: '2', name: 'FOIA Releases', query: 'FOIA OR "freedom of information" OR declassified', platforms: ['twitter', 'news', 'youtube'], enabled: true },
    { id: '3', name: 'Financial Crimes', query: '"offshore accounts" OR "shell company" OR "money laundering"', platforms: ['twitter', 'reddit', 'news'], enabled: true },
    { id: '4', name: 'Intelligence Agencies', query: 'CIA OR FBI OR NSA declassified', platforms: ['news', 'reddit'], enabled: false },
  ];

  const mockStats = {
    total_posts: 12847,
    posts_last_24h: 342,
    active_queries: 3,
    posts_by_platform: {
      twitter: 5234,
      reddit: 3421,
      youtube: 1892,
      news: 1567,
      bluesky: 512,
      mastodon: 221
    },
    trending_entities: [
      { name: 'Jeffrey Epstein', mentions: 1247, change: '+23%' },
      { name: 'Ghislaine Maxwell', mentions: 892, change: '+15%' },
      { name: 'Deutsche Bank', mentions: 456, change: '+8%' },
      { name: 'Virgin Islands', mentions: 234, change: '+45%' },
    ],
    documents_processed: 24521,
    entities_extracted: 8934,
    relationships_found: 12456
  };

  // ===== EFFECTS =====
  useEffect(() => {
    // Initialize with mock data
    setPosts(mockPosts);
    setMonitorQueries(mockQueries);
    setStats(mockStats);
    
    // Simulate real-time updates
    const interval = setInterval(() => {
      if (isMonitoring) {
        // Add a random new post occasionally
        if (Math.random() > 0.7) {
          const newPost = {
            ...mockPosts[Math.floor(Math.random() * mockPosts.length)],
            id: Date.now().toString(),
            created_at: new Date().toISOString(),
            content: `[LIVE UPDATE] ${mockPosts[Math.floor(Math.random() * mockPosts.length)].content}`
          };
          setPosts(prev => [newPost, ...prev.slice(0, 99)]);
          
          // Show notification
          addNotification({
            type: 'info',
            title: 'New Post Detected',
            message: `@${newPost.author} on ${newPost.platform}`
          });
        }
      }
    }, 5000);
    
    return () => clearInterval(interval);
  }, [isMonitoring]);

  // ===== HELPERS =====
  const addNotification = (notif) => {
    const id = Date.now();
    setNotifications(prev => [...prev, { ...notif, id }]);
    setTimeout(() => {
      setNotifications(prev => prev.filter(n => n.id !== id));
    }, 5000);
  };

  const formatTimeAgo = (dateStr) => {
    const seconds = Math.floor((new Date() - new Date(dateStr)) / 1000);
    if (seconds < 60) return `${seconds}s ago`;
    if (seconds < 3600) return `${Math.floor(seconds / 60)}m ago`;
    if (seconds < 86400) return `${Math.floor(seconds / 3600)}h ago`;
    return `${Math.floor(seconds / 86400)}d ago`;
  };

  const formatNumber = (num) => {
    if (num >= 1000000) return `${(num / 1000000).toFixed(1)}M`;
    if (num >= 1000) return `${(num / 1000).toFixed(1)}K`;
    return num.toString();
  };

  const getPlatformIcon = (platform) => {
    switch (platform) {
      case 'twitter': return <Twitter className="w-4 h-4" />;
      case 'reddit': return <MessageSquare className="w-4 h-4" />;
      case 'youtube': return <Youtube className="w-4 h-4" />;
      case 'news': return <Newspaper className="w-4 h-4" />;
      case 'bluesky': return <Globe className="w-4 h-4" />;
      case 'mastodon': return <Network className="w-4 h-4" />;
      default: return <Globe className="w-4 h-4" />;
    }
  };

  const getPlatformColor = (platform) => {
    switch (platform) {
      case 'twitter': return 'text-blue-400 bg-blue-400/10';
      case 'reddit': return 'text-orange-400 bg-orange-400/10';
      case 'youtube': return 'text-red-400 bg-red-400/10';
      case 'news': return 'text-emerald-400 bg-emerald-400/10';
      case 'bluesky': return 'text-sky-400 bg-sky-400/10';
      case 'mastodon': return 'text-purple-400 bg-purple-400/10';
      default: return 'text-gray-400 bg-gray-400/10';
    }
  };

  const getSentimentColor = (sentiment) => {
    switch (sentiment) {
      case 'positive': return 'text-green-400';
      case 'negative': return 'text-red-400';
      default: return 'text-gray-400';
    }
  };

  // ===== VOICE CONTROL =====
  const startListening = () => {
    if ('webkitSpeechRecognition' in window || 'SpeechRecognition' in window) {
      const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
      const recognition = new SpeechRecognition();
      recognition.continuous = false;
      recognition.interimResults = true;
      
      recognition.onresult = (event) => {
        const transcript = Array.from(event.results)
          .map(result => result[0].transcript)
          .join('');
        setSearchQuery(transcript);
      };
      
      recognition.onend = () => setIsListening(false);
      recognition.start();
      setIsListening(true);
    }
  };

  const speak = (text) => {
    if (voiceEnabled && 'speechSynthesis' in window) {
      const utterance = new SpeechSynthesisUtterance(text);
      utterance.rate = 1.0;
      utterance.pitch = 1.0;
      window.speechSynthesis.speak(utterance);
    }
  };

  // ===== THEME =====
  const theme = darkMode ? {
    bg: 'bg-gray-950',
    bgSecondary: 'bg-gray-900',
    bgTertiary: 'bg-gray-800',
    text: 'text-gray-100',
    textSecondary: 'text-gray-400',
    border: 'border-gray-800',
    accent: 'text-amber-400',
    accentBg: 'bg-amber-400/10',
  } : {
    bg: 'bg-gray-50',
    bgSecondary: 'bg-white',
    bgTertiary: 'bg-gray-100',
    text: 'text-gray-900',
    textSecondary: 'text-gray-600',
    border: 'border-gray-200',
    accent: 'text-amber-600',
    accentBg: 'bg-amber-100',
  };

  // ===== RENDER COMPONENTS =====
  
  // Navigation Items
  const navItems = [
    { id: 'dashboard', icon: Activity, label: 'Dashboard' },
    { id: 'monitor', icon: Radio, label: 'Live Monitor' },
    { id: 'knowledge', icon: BookOpen, label: 'Knowledge Base' },
    { id: 'entities', icon: Users, label: 'Entity Network' },
    { id: 'timeline', icon: Calendar, label: 'Timeline' },
    { id: 'board', icon: Target, label: 'Investigation Board' },
    { id: 'sources', icon: FileText, label: 'FOIA Sources' },
  ];

  // Sidebar
  const Sidebar = () => (
    <div className={`${theme.bgSecondary} border-r ${theme.border} flex flex-col transition-all duration-300 ${sidebarCollapsed ? 'w-16' : 'w-64'}`}>
      {/* Logo */}
      <div className={`p-4 border-b ${theme.border} flex items-center gap-3`}>
        <div className="w-10 h-10 rounded-lg bg-gradient-to-br from-amber-400 to-red-600 flex items-center justify-center">
          <Eye className="w-6 h-6 text-white" />
        </div>
        {!sidebarCollapsed && (
          <div>
            <h1 className={`font-bold ${theme.text}`}>SHADOW</h1>
            <p className={`text-xs ${theme.textSecondary}`}>Truth Seeker Platform</p>
          </div>
        )}
      </div>
      
      {/* Navigation */}
      <nav className="flex-1 p-2 space-y-1">
        {navItems.map(item => (
          <button
            key={item.id}
            onClick={() => setCurrentView(item.id)}
            className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-lg transition-all ${
              currentView === item.id 
                ? `${theme.accentBg} ${theme.accent}` 
                : `${theme.textSecondary} hover:${theme.bgTertiary} hover:${theme.text}`
            }`}
          >
            <item.icon className="w-5 h-5 flex-shrink-0" />
            {!sidebarCollapsed && <span className="font-medium">{item.label}</span>}
          </button>
        ))}
      </nav>
      
      {/* Bottom controls */}
      <div className={`p-4 border-t ${theme.border} space-y-2`}>
        {/* Monitoring status */}
        <button
          onClick={() => {
            setIsMonitoring(!isMonitoring);
            speak(isMonitoring ? 'Monitoring paused' : 'Monitoring started');
          }}
          className={`w-full flex items-center justify-center gap-2 px-3 py-2 rounded-lg transition-all ${
            isMonitoring 
              ? 'bg-green-500/20 text-green-400 border border-green-500/50' 
              : `${theme.bgTertiary} ${theme.textSecondary}`
          }`}
        >
          {isMonitoring ? <Radio className="w-4 h-4 animate-pulse" /> : <Pause className="w-4 h-4" />}
          {!sidebarCollapsed && <span>{isMonitoring ? 'LIVE' : 'Paused'}</span>}
        </button>
        
        {/* Voice toggle */}
        <button
          onClick={() => setVoiceEnabled(!voiceEnabled)}
          className={`w-full flex items-center justify-center gap-2 px-3 py-2 rounded-lg ${theme.bgTertiary} ${theme.textSecondary}`}
        >
          {voiceEnabled ? <Volume2 className="w-4 h-4" /> : <VolumeX className="w-4 h-4" />}
          {!sidebarCollapsed && <span>{voiceEnabled ? 'Voice On' : 'Voice Off'}</span>}
        </button>
        
        {/* Theme toggle */}
        <button
          onClick={() => setDarkMode(!darkMode)}
          className={`w-full flex items-center justify-center gap-2 px-3 py-2 rounded-lg ${theme.bgTertiary} ${theme.textSecondary}`}
        >
          {darkMode ? <Sun className="w-4 h-4" /> : <Moon className="w-4 h-4" />}
          {!sidebarCollapsed && <span>{darkMode ? 'Light Mode' : 'Dark Mode'}</span>}
        </button>
        
        {/* Collapse toggle */}
        <button
          onClick={() => setSidebarCollapsed(!sidebarCollapsed)}
          className={`w-full flex items-center justify-center px-3 py-2 rounded-lg ${theme.bgTertiary} ${theme.textSecondary}`}
        >
          {sidebarCollapsed ? <ChevronRight className="w-4 h-4" /> : <ChevronDown className="w-4 h-4 rotate-90" />}
        </button>
      </div>
    </div>
  );

  // Search Bar
  const SearchBar = () => (
    <div className={`${theme.bgSecondary} border-b ${theme.border} p-4`}>
      <div className="flex items-center gap-4">
        <div className="flex-1 relative">
          <Search className={`absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 ${theme.textSecondary}`} />
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Search across all sources... (try: 'offshore accounts' or 'flight logs')"
            className={`w-full pl-10 pr-12 py-3 rounded-xl ${theme.bgTertiary} ${theme.text} border ${theme.border} focus:outline-none focus:ring-2 focus:ring-amber-400/50`}
          />
          <button
            onClick={isListening ? () => setIsListening(false) : startListening}
            className={`absolute right-3 top-1/2 -translate-y-1/2 p-1 rounded-lg transition-colors ${
              isListening ? 'text-red-400 bg-red-400/10' : theme.textSecondary
            }`}
          >
            {isListening ? <MicOff className="w-5 h-5 animate-pulse" /> : <Mic className="w-5 h-5" />}
          </button>
        </div>
        
        {/* Quick filters */}
        <div className="flex items-center gap-2">
          {['all', 'twitter', 'reddit', 'youtube', 'news'].map(platform => (
            <button
              key={platform}
              onClick={() => setFilterPlatform(platform)}
              className={`px-3 py-2 rounded-lg text-sm font-medium transition-all ${
                filterPlatform === platform 
                  ? `${theme.accent} ${theme.accentBg}` 
                  : `${theme.textSecondary} ${theme.bgTertiary}`
              }`}
            >
              {platform === 'all' ? 'All' : platform.charAt(0).toUpperCase() + platform.slice(1)}
            </button>
          ))}
        </div>
        
        {/* Add query button */}
        <button
          onClick={() => setShowAddQuery(true)}
          className="flex items-center gap-2 px-4 py-2 rounded-lg bg-amber-500 text-black font-medium hover:bg-amber-400 transition-colors"
        >
          <Plus className="w-4 h-4" />
          Add Query
        </button>
      </div>
    </div>
  );

  // Dashboard View
  const Dashboard = () => (
    <div className="p-6 space-y-6">
      {/* Stats Grid */}
      <div className="grid grid-cols-4 gap-4">
        {[
          { label: 'Posts Collected', value: formatNumber(stats.total_posts), icon: MessageSquare, color: 'text-blue-400' },
          { label: 'Last 24 Hours', value: formatNumber(stats.posts_last_24h), icon: Clock, color: 'text-green-400' },
          { label: 'Documents Processed', value: formatNumber(stats.documents_processed), icon: FileText, color: 'text-amber-400' },
          { label: 'Entities Found', value: formatNumber(stats.entities_extracted), icon: Users, color: 'text-purple-400' },
        ].map((stat, i) => (
          <div key={i} className={`${theme.bgSecondary} rounded-xl p-4 border ${theme.border}`}>
            <div className="flex items-center justify-between mb-2">
              <stat.icon className={`w-5 h-5 ${stat.color}`} />
              <span className={`text-xs ${theme.textSecondary}`}>↑ 12%</span>
            </div>
            <p className={`text-2xl font-bold ${theme.text}`}>{stat.value}</p>
            <p className={`text-sm ${theme.textSecondary}`}>{stat.label}</p>
          </div>
        ))}
      </div>
      
      {/* Main content grid */}
      <div className="grid grid-cols-3 gap-6">
        {/* Live Feed */}
        <div className={`col-span-2 ${theme.bgSecondary} rounded-xl border ${theme.border}`}>
          <div className={`p-4 border-b ${theme.border} flex items-center justify-between`}>
            <div className="flex items-center gap-2">
              <Radio className={`w-5 h-5 ${isMonitoring ? 'text-green-400 animate-pulse' : theme.textSecondary}`} />
              <h2 className={`font-semibold ${theme.text}`}>Live Social Feed</h2>
              {isMonitoring && <span className="px-2 py-0.5 text-xs bg-green-500/20 text-green-400 rounded-full">LIVE</span>}
            </div>
            <button className={`p-2 rounded-lg ${theme.bgTertiary}`}>
              <RefreshCw className={`w-4 h-4 ${theme.textSecondary}`} />
            </button>
          </div>
          
          <div className="divide-y divide-gray-800 max-h-[500px] overflow-y-auto">
            {posts.filter(p => filterPlatform === 'all' || p.platform === filterPlatform).map(post => (
              <div 
                key={post.id} 
                onClick={() => setSelectedPost(post)}
                className={`p-4 hover:${theme.bgTertiary} cursor-pointer transition-colors`}
              >
                <div className="flex items-start gap-3">
                  <div className={`p-2 rounded-lg ${getPlatformColor(post.platform)}`}>
                    {getPlatformIcon(post.platform)}
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 mb-1">
                      <span className={`font-medium ${theme.text}`}>@{post.author}</span>
                      <span className={`text-xs ${theme.textSecondary}`}>{formatTimeAgo(post.created_at)}</span>
                      <span className={`text-xs ${getSentimentColor(post.sentiment)}`}>
                        {post.sentiment === 'positive' ? '📈' : post.sentiment === 'negative' ? '📉' : ''}
                      </span>
                    </div>
                    {post.title && <p className={`font-medium ${theme.text} mb-1`}>{post.title}</p>}
                    <p className={`${theme.textSecondary} text-sm line-clamp-2`}>{post.content}</p>
                    
                    {/* Matched queries */}
                    <div className="flex items-center gap-2 mt-2">
                      {post.matched_queries?.map((q, i) => (
                        <span key={i} className={`text-xs px-2 py-0.5 rounded-full ${theme.accentBg} ${theme.accent}`}>
                          {q}
                        </span>
                      ))}
                    </div>
                    
                    {/* Engagement */}
                    <div className="flex items-center gap-4 mt-2">
                      {post.likes > 0 && (
                        <span className={`text-xs ${theme.textSecondary} flex items-center gap-1`}>
                          <Heart className="w-3 h-3" /> {formatNumber(post.likes)}
                        </span>
                      )}
                      {post.shares > 0 && (
                        <span className={`text-xs ${theme.textSecondary} flex items-center gap-1`}>
                          <Repeat className="w-3 h-3" /> {formatNumber(post.shares)}
                        </span>
                      )}
                      {post.comments > 0 && (
                        <span className={`text-xs ${theme.textSecondary} flex items-center gap-1`}>
                          <MessageSquare className="w-3 h-3" /> {formatNumber(post.comments)}
                        </span>
                      )}
                      {post.views > 0 && (
                        <span className={`text-xs ${theme.textSecondary} flex items-center gap-1`}>
                          <Eye className="w-3 h-3" /> {formatNumber(post.views)}
                        </span>
                      )}
                    </div>
                  </div>
                  <button className={`p-2 rounded-lg ${theme.bgTertiary} opacity-0 group-hover:opacity-100`}>
                    <ExternalLink className={`w-4 h-4 ${theme.textSecondary}`} />
                  </button>
                </div>
              </div>
            ))}
          </div>
        </div>
        
        {/* Right sidebar */}
        <div className="space-y-4">
          {/* Trending Entities */}
          <div className={`${theme.bgSecondary} rounded-xl border ${theme.border}`}>
            <div className={`p-4 border-b ${theme.border}`}>
              <h3 className={`font-semibold ${theme.text} flex items-center gap-2`}>
                <TrendingUp className="w-4 h-4 text-amber-400" />
                Trending Entities
              </h3>
            </div>
            <div className="p-4 space-y-3">
              {stats.trending_entities?.map((entity, i) => (
                <div key={i} className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <span className={`w-6 h-6 rounded-full ${theme.bgTertiary} flex items-center justify-center text-xs ${theme.textSecondary}`}>
                      {i + 1}
                    </span>
                    <span className={`${theme.text} font-medium`}>{entity.name}</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <span className={`text-sm ${theme.textSecondary}`}>{entity.mentions}</span>
                    <span className="text-xs text-green-400">{entity.change}</span>
                  </div>
                </div>
              ))}
            </div>
          </div>
          
          {/* Active Queries */}
          <div className={`${theme.bgSecondary} rounded-xl border ${theme.border}`}>
            <div className={`p-4 border-b ${theme.border}`}>
              <h3 className={`font-semibold ${theme.text} flex items-center gap-2`}>
                <Target className="w-4 h-4 text-amber-400" />
                Active Queries
              </h3>
            </div>
            <div className="p-4 space-y-2">
              {monitorQueries.filter(q => q.enabled).map(query => (
                <div key={query.id} className={`p-3 rounded-lg ${theme.bgTertiary}`}>
                  <div className="flex items-center justify-between mb-1">
                    <span className={`font-medium ${theme.text}`}>{query.name}</span>
                    <span className="w-2 h-2 rounded-full bg-green-400 animate-pulse" />
                  </div>
                  <p className={`text-xs ${theme.textSecondary} truncate`}>{query.query}</p>
                  <div className="flex gap-1 mt-2">
                    {query.platforms.map(p => (
                      <span key={p} className={`p-1 rounded ${getPlatformColor(p)}`}>
                        {getPlatformIcon(p)}
                      </span>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          </div>
          
          {/* Platform Distribution */}
          <div className={`${theme.bgSecondary} rounded-xl border ${theme.border}`}>
            <div className={`p-4 border-b ${theme.border}`}>
              <h3 className={`font-semibold ${theme.text} flex items-center gap-2`}>
                <PieChart className="w-4 h-4 text-amber-400" />
                Platform Distribution
              </h3>
            </div>
            <div className="p-4 space-y-2">
              {Object.entries(stats.posts_by_platform || {}).map(([platform, count]) => (
                <div key={platform} className="flex items-center gap-3">
                  <span className={`p-1.5 rounded ${getPlatformColor(platform)}`}>
                    {getPlatformIcon(platform)}
                  </span>
                  <div className="flex-1">
                    <div className="flex justify-between text-sm mb-1">
                      <span className={theme.text}>{platform}</span>
                      <span className={theme.textSecondary}>{formatNumber(count)}</span>
                    </div>
                    <div className={`h-1.5 rounded-full ${theme.bgTertiary}`}>
                      <div 
                        className="h-full rounded-full bg-amber-400"
                        style={{ width: `${(count / stats.total_posts) * 100}%` }}
                      />
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );

  // Live Monitor View
  const LiveMonitor = () => (
    <div className="p-6">
      <div className="grid grid-cols-2 gap-6">
        {/* Query Management */}
        <div className={`${theme.bgSecondary} rounded-xl border ${theme.border}`}>
          <div className={`p-4 border-b ${theme.border} flex items-center justify-between`}>
            <h2 className={`font-semibold ${theme.text}`}>Monitoring Queries</h2>
            <button
              onClick={() => setShowAddQuery(true)}
              className="flex items-center gap-1 px-3 py-1.5 rounded-lg bg-amber-500 text-black text-sm font-medium"
            >
              <Plus className="w-4 h-4" /> Add
            </button>
          </div>
          <div className="p-4 space-y-3">
            {monitorQueries.map(query => (
              <div key={query.id} className={`p-4 rounded-lg ${theme.bgTertiary}`}>
                <div className="flex items-center justify-between mb-2">
                  <span className={`font-medium ${theme.text}`}>{query.name}</span>
                  <label className="relative inline-flex items-center cursor-pointer">
                    <input 
                      type="checkbox" 
                      checked={query.enabled}
                      onChange={() => {
                        setMonitorQueries(prev => prev.map(q => 
                          q.id === query.id ? { ...q, enabled: !q.enabled } : q
                        ));
                      }}
                      className="sr-only peer" 
                    />
                    <div className="w-9 h-5 bg-gray-700 peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:bg-green-500 after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:rounded-full after:h-4 after:w-4 after:transition-all"></div>
                  </label>
                </div>
                <p className={`text-sm ${theme.textSecondary} mb-3 font-mono`}>{query.query}</p>
                <div className="flex items-center gap-2">
                  {query.platforms.map(p => (
                    <span key={p} className={`px-2 py-1 rounded text-xs ${getPlatformColor(p)}`}>
                      {p}
                    </span>
                  ))}
                </div>
              </div>
            ))}
          </div>
        </div>
        
        {/* Real-time feed */}
        <div className={`${theme.bgSecondary} rounded-xl border ${theme.border}`}>
          <div className={`p-4 border-b ${theme.border} flex items-center justify-between`}>
            <div className="flex items-center gap-2">
              <Radio className={`w-5 h-5 ${isMonitoring ? 'text-green-400 animate-pulse' : theme.textSecondary}`} />
              <h2 className={`font-semibold ${theme.text}`}>Real-time Stream</h2>
            </div>
            <button
              onClick={() => setIsMonitoring(!isMonitoring)}
              className={`px-4 py-2 rounded-lg font-medium ${
                isMonitoring 
                  ? 'bg-red-500/20 text-red-400' 
                  : 'bg-green-500/20 text-green-400'
              }`}
            >
              {isMonitoring ? 'Stop' : 'Start'} Monitoring
            </button>
          </div>
          <div className="max-h-[600px] overflow-y-auto divide-y divide-gray-800">
            {posts.slice(0, 20).map(post => (
              <div key={post.id} className="p-4">
                <div className="flex items-center gap-2 mb-2">
                  <span className={`p-1.5 rounded ${getPlatformColor(post.platform)}`}>
                    {getPlatformIcon(post.platform)}
                  </span>
                  <span className={`font-medium ${theme.text}`}>@{post.author}</span>
                  <span className={`text-xs ${theme.textSecondary}`}>{formatTimeAgo(post.created_at)}</span>
                </div>
                <p className={`${theme.textSecondary} text-sm`}>{post.content}</p>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );

  // Add Query Modal
  const AddQueryModal = () => {
    const [name, setName] = useState('');
    const [query, setQuery] = useState('');
    const [platforms, setPlatforms] = useState(['twitter', 'reddit', 'news']);
    
    const handleSubmit = () => {
      const newQuery = {
        id: Date.now().toString(),
        name,
        query,
        platforms,
        enabled: true
      };
      setMonitorQueries(prev => [...prev, newQuery]);
      setShowAddQuery(false);
      addNotification({ type: 'success', title: 'Query Added', message: `Now monitoring: ${name}` });
      speak(`Added monitoring query: ${name}`);
    };
    
    return (
      <div className="fixed inset-0 bg-black/80 flex items-center justify-center z-50">
        <div className={`${theme.bgSecondary} rounded-2xl w-full max-w-lg border ${theme.border}`}>
          <div className={`p-4 border-b ${theme.border} flex items-center justify-between`}>
            <h2 className={`text-lg font-semibold ${theme.text}`}>Add Monitoring Query</h2>
            <button onClick={() => setShowAddQuery(false)} className={theme.textSecondary}>
              <X className="w-5 h-5" />
            </button>
          </div>
          
          <div className="p-6 space-y-4">
            <div>
              <label className={`block text-sm font-medium ${theme.text} mb-2`}>Query Name</label>
              <input
                type="text"
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="e.g., Financial Networks"
                className={`w-full px-4 py-2 rounded-lg ${theme.bgTertiary} ${theme.text} border ${theme.border}`}
              />
            </div>
            
            <div>
              <label className={`block text-sm font-medium ${theme.text} mb-2`}>Search Query</label>
              <input
                type="text"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder='e.g., "shell company" OR "offshore" OR "wire transfer"'
                className={`w-full px-4 py-2 rounded-lg ${theme.bgTertiary} ${theme.text} border ${theme.border} font-mono text-sm`}
              />
              <p className={`text-xs ${theme.textSecondary} mt-1`}>
                Use OR for alternatives, quotes for exact phrases
              </p>
            </div>
            
            <div>
              <label className={`block text-sm font-medium ${theme.text} mb-2`}>Platforms</label>
              <div className="flex flex-wrap gap-2">
                {['twitter', 'reddit', 'youtube', 'news', 'bluesky', 'mastodon'].map(p => (
                  <button
                    key={p}
                    onClick={() => {
                      setPlatforms(prev => 
                        prev.includes(p) ? prev.filter(x => x !== p) : [...prev, p]
                      );
                    }}
                    className={`px-3 py-2 rounded-lg flex items-center gap-2 ${
                      platforms.includes(p) 
                        ? getPlatformColor(p) + ' ring-2 ring-amber-400' 
                        : theme.bgTertiary + ' ' + theme.textSecondary
                    }`}
                  >
                    {getPlatformIcon(p)}
                    <span className="text-sm capitalize">{p}</span>
                  </button>
                ))}
              </div>
            </div>
          </div>
          
          <div className={`p-4 border-t ${theme.border} flex justify-end gap-3`}>
            <button 
              onClick={() => setShowAddQuery(false)}
              className={`px-4 py-2 rounded-lg ${theme.bgTertiary} ${theme.textSecondary}`}
            >
              Cancel
            </button>
            <button
              onClick={handleSubmit}
              disabled={!name || !query}
              className="px-4 py-2 rounded-lg bg-amber-500 text-black font-medium disabled:opacity-50"
            >
              Add Query
            </button>
          </div>
        </div>
      </div>
    );
  };

  // Notifications
  const Notifications = () => (
    <div className="fixed bottom-4 right-4 space-y-2 z-50">
      {notifications.map(notif => (
        <div 
          key={notif.id}
          className={`${theme.bgSecondary} border ${theme.border} rounded-lg p-4 shadow-2xl animate-slide-in flex items-start gap-3 min-w-[300px]`}
        >
          {notif.type === 'success' && <CheckCircle className="w-5 h-5 text-green-400 flex-shrink-0" />}
          {notif.type === 'error' && <AlertTriangle className="w-5 h-5 text-red-400 flex-shrink-0" />}
          {notif.type === 'info' && <Bell className="w-5 h-5 text-blue-400 flex-shrink-0" />}
          <div>
            <p className={`font-medium ${theme.text}`}>{notif.title}</p>
            <p className={`text-sm ${theme.textSecondary}`}>{notif.message}</p>
          </div>
        </div>
      ))}
    </div>
  );

  // Placeholder views
  const PlaceholderView = ({ title, icon: Icon }) => (
    <div className="flex-1 flex items-center justify-center">
      <div className="text-center">
        <Icon className={`w-16 h-16 ${theme.textSecondary} mx-auto mb-4`} />
        <h2 className={`text-xl font-semibold ${theme.text} mb-2`}>{title}</h2>
        <p className={theme.textSecondary}>This view integrates with the main SHADOW platform</p>
      </div>
    </div>
  );

  // ===== MAIN RENDER =====
  return (
    <div className={`h-screen flex ${theme.bg}`}>
      <Sidebar />
      
      <div className="flex-1 flex flex-col overflow-hidden">
        <SearchBar />
        
        <div className="flex-1 overflow-y-auto">
          {currentView === 'dashboard' && <Dashboard />}
          {currentView === 'monitor' && <LiveMonitor />}
          {currentView === 'knowledge' && <PlaceholderView title="Knowledge Base" icon={BookOpen} />}
          {currentView === 'entities' && <PlaceholderView title="Entity Network" icon={Users} />}
          {currentView === 'timeline' && <PlaceholderView title="Timeline" icon={Calendar} />}
          {currentView === 'board' && <PlaceholderView title="Investigation Board" icon={Target} />}
          {currentView === 'sources' && <PlaceholderView title="FOIA Sources" icon={FileText} />}
        </div>
      </div>
      
      {showAddQuery && <AddQueryModal />}
      <Notifications />
      
      <style jsx global>{`
        @keyframes slide-in {
          from {
            transform: translateX(100%);
            opacity: 0;
          }
          to {
            transform: translateX(0);
            opacity: 1;
          }
        }
        .animate-slide-in {
          animation: slide-in 0.3s ease-out;
        }
      `}</style>
    </div>
  );
}
