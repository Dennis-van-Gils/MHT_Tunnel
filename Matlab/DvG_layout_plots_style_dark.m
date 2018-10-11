function DvG_layout_plots_style_dark(varargin)

clr_bkg_fig = [.25 .25 .25];
clr_bkg_gca = [20 20 20]/255;
clr_grid = [245 237 225]/255;
%clr_turq = [0.68 0.92 1];

if nargin == 0
  h_figs = gcf;
else
  h_figs = varargin{1};
end

nFigs = length(h_figs);
for iFig = 1:nFigs
  h_fig = h_figs(iFig);
  set(h_fig, 'PaperType', 'A4')
  set(h_fig, 'Color', clr_bkg_fig)
  set(h_fig, 'Renderer', 'Painters')

  h_axs = findall(h_fig, 'Type', 'axes');  
  for i_ax = 1:length(h_axs)
    h_ax    = h_axs(i_ax);
    h_title = get(h_ax, 'Title');
    h_lblX  = get(h_ax, 'XLabel');
    h_lblY  = get(h_ax, 'YLabel');
    h_leg   = findobj(h_fig, 'Tag', 'legend');

    box(h_ax, 'on')
    set(h_ax, 'XGrid', 'off')
    set(h_ax, 'YGrid', 'on')
    set(h_ax, 'GridLineStyle', ':')
    set(h_ax, 'Color', clr_bkg_gca)
    set(h_ax, 'XColor', clr_grid)
    set(h_ax, 'YColor', clr_grid)
    set(h_ax, 'TickLength', [0.02 0.02])
    set(h_ax, 'FontSize', 10)
    set(h_ax, 'Linewidth', 1)
    
    h_leg_text = findobj(h_leg, 'Type', 'Text');
    set(h_leg_text, 'Color', clr_grid)
    set(h_leg_text, 'FontSize', 10)

    set(h_title, 'FontSize', 12, 'Color', clr_grid)
    %set(h_lblX, 'Interpreter', 'Latex')
    %set(h_lblY, 'Interpreter', 'Latex')
    set(h_lblX, 'FontSize', 12, 'Color', clr_grid)
    set(h_lblY, 'FontSize', 12, 'Color', clr_grid)

    %set(h_ax, 'Position', [.16 .16 .78 .705])
  end
  
  h_txt = findall(h_fig, 'Type', 'text');
  set(h_txt, 'Color', clr_grid)
end