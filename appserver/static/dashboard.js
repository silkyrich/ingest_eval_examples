/* TODO: jink to replace theme_utils with that from core */
require.config({
    paths: {
        "app": "../app",
        showdown: '../app/ingest_eval_examples/components/srcviewer/contrib/showdown',
        theme_utils: '../app/ingest_eval_examples/theme_utils'
    }
});

require([
    'jquery',
    'underscore',
    'splunkjs/mvc/simplexml/controller',
    'splunk.util',
    'backbone',
    'showdown',
    'app/ingest_eval_examples/components/srcviewer/srcviewer',
    'theme_utils'
], function($, _, DashboardController, SplunkUtil, Backbone, Showdown, SourceViewer, themeUtils) {
    // Disable Bootstrap auto discovery
    $('body').off('.data-api');
    // Open external links in new window
    $('.external[href]').bind('click', function(e){
        e.preventDefault();
        window.open($(e.currentTarget).attr('href'));
    });

    var APP = 'ingest_eval_examples';

    var exampleInfoCollection = new Backbone.Collection();
    var exampleInfoLoaded = exampleInfoCollection.fetch({
        url: SplunkUtil.make_url('/static/app/' + APP + '/exampleInfo.json'),
        cache: true
    });

    var isDarkTheme = themeUtils.getCurrentTheme && themeUtils.getCurrentTheme() === 'dark';

    var bannerTemplate = '<div class="dashboard-banner"><%= message %></div>';



    DashboardController.onReady(function() {
        DashboardController.onViewModelLoad(function() {
            var view = DashboardController.model.view;
            var $xml = view.get$XML();
            var root = $xml.find(':eq(0)');

            if (SplunkUtil.normalizeBoolean(root.attr('showsource')) === false) {
                return;
            }

            $.when(exampleInfoLoaded).then(function(){

                var model = exampleInfoCollection.get(view.entry.get('name'));
                if(!model) {
                    model = new Backbone.Model({
                        shortDescription: '',
                        description: '',
                        related_links: []
                    });
                }

                // Look up view names for related links using examplesInfo.json
                if(model.has('related_links')) {
                    var translatedLinks = _(model.get('related_links')).map(function(link){
                        var label = link;
                        var info = exampleInfoCollection.get(link);
                        if(info) {
                            label = info.get('title');
                        }
                        return { href: link, label: label };
                    });
                    model.set('related_links', translatedLinks);
                }

                // Fetch HTML file for the description
                if(model.has('description-url') || !model.has('description')) {
                    var url = model.get('description-url');
                    if(!url) {
                        url = '/static/app/' + APP + '/description/' + model.get('id') + '.md';
                    }
                    $.ajax({
                        url: SplunkUtil.make_url(url),
                        dataType: 'text',
                        success: function(text){
                            model.set('description', text);
                        }
                    });
                }

                var sourceFileModels = new Backbone.Collection();

                sourceFileModels.add({
                    name: view.entry.get('name') + '.xml',
                    content: view.entry.content.get('eai:data')
                });

                // Add custom scripts to the viewer
                var customScripts = root.attr('script');
                if (customScripts) {
                    _(customScripts.split(',')).chain().map($.trim).each(function(script) {
                        var codeModel = new Backbone.Model({
                            name: script,
                            url: '/static/app/' + APP + '/' + script
                        });
                        sourceFileModels.add(codeModel);
                        $.ajax({
                            url: SplunkUtil.make_url('/static/app/' + APP + '/' + script),
                            dataType: 'text',
                            success: function(source) {
                                codeModel.set('content', source);
                            },
                            error: function() {
                            }
                        });
                    });
                }

                // Add custom stylesheets to the viewer
                var customStylesheets = root.attr('stylesheet');
                if (customStylesheets) {
                    _(customStylesheets.split(',')).chain().map($.trim).each(function(stylesheet) {
                        var codeModel = new Backbone.Model({
                            name: stylesheet,
                            url: '/static/app/' + APP + '/' + stylesheet,
                            lang: 'css'
                        });
                        sourceFileModels.add(codeModel);
                        $.ajax({
                            url: SplunkUtil.make_url('/static/app/' + APP + '/' + stylesheet),
                            dataType: 'text',
                            success: function(source) {
                                codeModel.set('content', source);
                            },
                            error: function() {
                            }
                        });
                    });
                }

                if (model.has("banner")) {
                    var url = '/static/app/' + APP + '/banner/' + model.get('banner') + '.md';
                    $.ajax({
                        url: SplunkUtil.make_url(url),
                        dataType: 'text',
                        success: function(text){
                            var markdown = new Showdown.converter();
                            var banner = $(_.template(bannerTemplate, {message: markdown.makeHtml(text)}));
                            if (isDarkTheme) {
                              banner.addClass('dark');
                            }
                            $('.main-section-body.dashboard-body').prepend($(banner));
                        }
                    });
                }

                // Load additional source files from examplesInfo.json
                if(model.has('sourceFiles')) {
                    _(model.get('sourceFiles')).each(function(link){
                        var filename = link.split('/').slice(-1)[0];
                        var codeModel = new Backbone.Model({
                            name: filename,
                            lang: filename.slice('-4') === '.css' ? 'css' : null,
                            url: link
                        });
                        sourceFileModels.add(codeModel);
                        $.ajax({
                            url: SplunkUtil.make_url(link),
                            dataType: 'text',
                            success: function(source) {
                                codeModel.set('content', source);
                            },
                            error: function() {
                            }
                        });
                    });
                }

                // Create the source code viewer
                var footer = $('#footer');
                var SourceViewerEl = $('<div/>');
                if (footer.length > 0) {
                  SourceViewerEl.insertBefore(footer);
                } else {
                  SourceViewerEl.appendTo($('body'));
                }

                new SourceViewer({
                    model: model,
                    collection: sourceFileModels,
                    el: SourceViewerEl
                }).render();
                $('.main-section-body.dashboard-body').css('min-height', '100px');
            });
        });
    });
})
;
