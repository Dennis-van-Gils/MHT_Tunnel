function MHT_saveFig(h, fileName, outputSubDir)

% Saves the figure with handle 'h' to disk relative to the current working
% directory, wih filename 'fileName'.
% The given 'outputSubDir' is created when necessary.
%
% Dennis van Gils
% 11-08-2010

% ------------------------------------------------------------------------
%   Check input arguments
% ------------------------------------------------------------------------

switch nargin
  case 0
    h = gcf;
    fileName = 'figure';
    outputDir = '';
  case 1
    fileName = 'figure';
    outputDir = '';
  case 2
    outputDir = '';
  case 3
    if isempty(outputSubDir)
      outputDir = '';
    else
      % Create directory when necessary
      [s, mess, messid] = mkdir(pwd, outputSubDir);                         %#ok<NASGU>
      outputDir = [outputSubDir '\'];
    end
end

% ------------------------------------------------------------------------
%   Save figures
% ------------------------------------------------------------------------

fn = [outputDir fileName];

figure(h)

% Hack to work around bug 'eps2pdf.m'
% Bug: legend box can be too small, crushing the text together
% Only needed when legends are displayed
% And only apply when figure does not contain subplots
h_leg = findall(gcf, 'Tag', 'legend');
if ~isempty(h_leg) && (length(get(h, 'children')) <= 2)
  tmp_ax = gca;
  set(gca, 'Units', 'pixels')
  tmp_axPos = get(gca, 'Position');
  set(h_leg, 'Position', get(h_leg, 'Position'))
  set(tmp_ax, 'Position', tmp_axPos )
end

saveas(h, [fn, '.fig'])
set(h, 'PaperPositionMode', 'auto')
set(h, 'PaperOrientation', 'portrait')
set(h, 'InvertHardcopy', 'off')

set(h, 'Units', 'Centimeters');
pos = get(h, 'Position');
set(h, 'PaperUnits', 'Centimeters', 'PaperSize', [pos(3), pos(4)])

print('-r120', '-dpng', [fn '.png'])
print('-r0', '-dpdf', [fn '.pdf'])
%export_fig('-pdf', [fn '.pdf'])
disp(['Saved figure: ' fn])