odoo.define('multichannel_amazon.AWSMatchingProducts', function (require) {
    "use strict";

    const core = require('web.core');
    const AbstractAction = require('web.AbstractAction');
    const qweb = core.qweb;

    const AWSMatchingProducts = AbstractAction.extend({
        template: 'AWSMatchingProducts',
        events: {
            'click .show-variants-link': 'onShowVariants',
            'change #input-query': 'onChangeQuery',
            'click #btn-find-product': 'onFindProduct',
            'change .select-product': 'onChangeSelectedProduct'
        },
        init: function(parent, options){
            this._super.apply(this, arguments);
            let context = options.context;
            this.product_tmpl = context.product_tmpl;
            this.channel_id = context.channel_id;
            this.query = null;
            this.products = context.products;
            this.mode = context.mode;
            this.channel_variant_id = context.channel_variant_id;
            this.selected_parent_asin = null;
            this.marketplace_id = context.marketplace_id;
            this.mapped_variants = [];
        },
        renderButtons: function ($node) {
            this.$footer_buttons = $(qweb.render('AWSMatchingProducts.buttons'));
            this.$footer_buttons.appendTo($node);
            this.$footer_buttons.on('click', '.btn-cancel', this._onCancel.bind(this));
            this.$footer_buttons.on('click', '.btn-list-product', this.onConfirm.bind(this));
            this.$footer_buttons.on('click', '.btn-select-product', this.onConfirm.bind(this));
        },
        _onCancel: function(){
            this.do_action({type: 'ir.actions.act_window_close'});
        },
        toggleShowVariantsLink: function ($el) {
            $el.find('.text-link').text(`${$el.hasClass('show') ? 'Hide' : 'Show'} Amazon Variants`);
            $el.find('span').toggleClass('fa-caret-down fa-caret-up');
            $el.toggleClass('show hide');
        },
        showVariantSection($section, data) {
            $section.slideDown();
            if (data['Variants'] === undefined){
                let id_list = data['ChildASIN'];
                this._rpc({
                    model: 'ecommerce.channel',
                    method: 'amazon_get_matching_product',
                    args: [[this.channel_id], id_list],
                })
                .then(variants => {
                    data['Variants'] = Object.values(variants);
                    $section.empty().append(qweb.render("AWSMatchingVariantsResult", {product: data, widget: this}));
                    $section.data('loaded', 'true');
                });
            }
            else if ($section.data('loaded') !== 'true') {
                $section.empty().append(qweb.render("AWSMatchingVariantsResult", {product: data, widget: this}));
                $section.data('loaded', 'true');
            }
        },
        onShowVariants: function (ev) {
            let $cur = $(ev.currentTarget);
            this.$el.find('.show-variants-link.hide').not($cur).each((i, e) => {
                this.toggleShowVariantsLink($(e));
            });
            _.each(this.$el.find('section.variant-section'), function(e){
                $(e).slideUp();
            });
            if ($cur.hasClass('show')) {
                let parentAsin = String($cur.data('parent-asin'));
                let parentData = _.find(this.products, p => p['ASIN'] === parentAsin);
                let $section = this.$el.find('section.variant-section').filter((i, e) => {
                    return String($(e).data('parent-asin')) === parentAsin
                });
                this.showVariantSection($section, parentData);
            }
            this.toggleShowVariantsLink($cur);
        },
        _disableSelectedVariants: function(){
            let self = this;
            if (this.mode == 'list-product'){
                _.each(this.$el.find('.select-product'), function (e) {
                    if (String($(e).data('parent-asin')) === self.selected_parent_asin){
                        _.each($(e).find('option'), function(o){
                            if (self.mapped_variants.indexOf($(o).val()) === -1){
                                $(o).prop("disabled", false);
                            }else{
                                if ($(e).val() !== $(o).val()){
                                    $(o).prop("disabled", true);
                                }
                            }
                        })
                    }else{
                        _.each($(e).find('option'), function(o){
                            $(o).prop("disabled", false);
                        })
                    }
                })
            }
        },
        _resetSelectedParent: function(){
            let self = this;
            _.each(this.$el.find('.select-product'), function(e){
                if (String($(e).data('parent-asin')) !== self.selected_parent_asin){
                    $(e).val('0');
                }
            })
        },
        _getMappedVariants: function(){
            let self = this;
            this.mapped_variants = [];
            let $sections = _.filter(this.$el.find('.select-product'), function (e) {
                return String($(e).data('parent-asin')) === self.selected_parent_asin
            });
            _.each($sections, function (e) {
                let value = $(e).val();
                if (value !== '0' && value !== null){
                    self.mapped_variants.push(value);
                }
            });
            this._changeFooterButtonDisplay();
        },
        _changeFooterButtonDisplay: function () {
            let lpc = '.btn-list-product', spc = '.btn-select-product';
            let $button = this.$footer_buttons.find(this.mode === 'list-product' ? lpc : spc);
            $button.toggle(this.mapped_variants.length !== 0);
        },
        onChangeSelectedProduct: function (ev) {
            let parentAsin = String($(ev.currentTarget).data('parent-asin'));
            this.selected_parent_asin = parentAsin;
            let showingLink = this.$el.find('.show-variants-link.hide');
            if (showingLink && String(showingLink.data('parent-asin')) !== parentAsin) {
                showingLink.trigger('click');
            }

            if (this.mode == 'list-product'){
                this._resetSelectedParent();
                this._getMappedVariants();
                this._disableSelectedVariants();
            }else{
                let value = $(ev.currentTarget).val();
                let element = _.find(this.$el.find('.select-product:checked'), function(e){
                    return $(e).val() != '0' && $(e).val() != value});
                if (element){
                    $(element).prop("checked", false);
                }
                this.mapped_variants = this.$el.find('.select-product:checked');
                this._changeFooterButtonDisplay();
            }
        },
        onChangeQuery: function(ev){
            this.query = $(ev.currentTarget).val();
        },
        onFindProduct: function (ev) {
            let self = this;
            if (this.query){
                let $cur = $(ev.currentTarget);
                $cur.prop('disabled', true);
                self.$el.find('section.bottom').hide();
                self.$el.find('section.bottom-loader').show();

                let always = function () {
                    self.$el.find('section.bottom-loader').hide();
                    $cur.prop('disabled', false);
                };

                this._rpc({
                    model: 'ecommerce.channel',
                    method: 'amazon_list_matching_products',
                    args: [[self.channel_id], this.query, this.marketplace_id],
                }).then(function (products) {
                    self.products = products;
                    self.$el.find('section.bottom').empty().append(qweb.render("AWSMatchingProductsResult", {widget: self}));
                    self.$el.find('section.bottom').show();
                    always();
                }).guardedCatch(always);
            }
        },
        onConfirm: function(ev) {
            let $cur = $(ev.currentTarget);
            $cur.prop('disabled', true);
            let result = this.mode === 'list-product' ? this.listProduct() : this.selectProduct();
            result.guardedCatch(() => { $cur.prop('disabled', false); });
        },
        _getFormData: function() {
            let selected_parent_data = _.find(this.products, p => p['ASIN'] === this.selected_parent_asin);
            let variant_asin = {};
            if (this.mode == 'list-product'){
                let $selections = _.filter(this.$el.find('.select-product'), e => {
                    return String($(e).data('parent-asin')) === this.selected_parent_asin && $(e).val() !== '0'
                        && $(e).val() !== null});
                _.each($selections, function (e) {
                    if ($(e).hasClass('select-variant')) {
                        variant_asin[parseInt($(e).val())] = String($(e).data('variant-asin'));
                    } else {
                        variant_asin[parseInt($(e).val())] = String($(e).data('parent-asin'));
                    }
                });
            }else{
                let element = this.$el.find('input.select-product:checked');
                if ($(element).hasClass('select-variant')){
                    variant_asin[parseInt($(element).val())] = String($(element).data('variant-asin'));
                }else{
                    variant_asin[parseInt($(element).val())] = String($(element).data('parent-asin'));
                }
            }
            return [selected_parent_data, variant_asin];
        },
        listProduct: function () {
            let [selected_parent_data, variant_asin] = this._getFormData();
            return this._rpc({
                model: 'product.template',
                method: 'list_to_amazon',
                args: [[this.product_tmpl.id], this.channel_id, selected_parent_data, variant_asin, this.marketplace_id],
            }).then(action => {
               this.do_action(action);
            });
        },
        selectProduct: function () {
            let [selected_parent_data, variant_asin] = this._getFormData();
            if (_.size(variant_asin) === 1) {
                let asin = _.first(_.values(variant_asin));
                let selected_data = selected_parent_data['ASIN'] === asin ?
                        selected_parent_data : _.find(selected_parent_data['Variants'], p => p['ASIN'] === asin);
                return this._rpc({
                    model: 'product.channel.variant',
                    method: 'amazon_set_product',
                    args: [[this.channel_variant_id], selected_data],
                }).then(() => {
                    this.do_action({type: 'ir.actions.act_window_close'});
                });
            }
        }
    });

    core.action_registry.add('action.aws_matching_products', AWSMatchingProducts);

});
