function MHT = MHT_quickPlot(varargin)
% Dennis van Gils
% 11-10-2018

if nargin==1
  MHT = varargin{1};
else
  MHT = MHT_readFile();
end

% Python colors of the heater temperatures
cm = [199, 0  , 191; ...
      0  , 128, 255; ...
      0  , 255, 255; ...
      20 , 200, 20 ; ...
      255, 255, 0  ; ...
      255, 0  , 0  ]/255;

% Plot lay-out
set(0, 'DefaultLineLineWidth', 2)

% Run name for plotting
runName = strrep(MHT.filename, '_', '\_');

% Prepare figure
h1 = figure(1);
set(h1, 'Position', [10 10 1536 960])
clf
    
% -------------------------------------------------------------------------
%  Heater temperatures
% -------------------------------------------------------------------------

h1a = subplot(3, 2, 1);
for iTC = 1:12
  strField = sprintf('T_TC_%02i', iTC);
  if iTC <= 6
    width = 2;
    color = cm(iTC, :);
  else
    width = 4;
    color = cm(13-iTC, :);
  end
  
  plot(MHT.time, MHT.(strField), '-', ...
       'Color', color, 'LineWidth', width, ...
       'DisplayName', sprintf('#%02i', iTC))
  hold on
end
title(sprintf('%s\nHeater temperatures (\\pm2.2 K)', runName))
xlabel('time (s)')
ylabel('temperature (\circC)')
legend('Location', 'NEO');

% -------------------------------------------------------------------------
%  Tunnel temperatures
% -------------------------------------------------------------------------

h1b = subplot(3, 2, 3);  
plot(MHT.time, MHT.T_outlet, '-', ...
    'Color', cm(6, :), 'DisplayName', 'outlet')
hold on
plot(MHT.time, MHT.T_inlet, '-', ...
     'Color', cm(2, :), 'DisplayName', 'inlet')
if isfield(MHT, 'T_ambient')
   plot(MHT.time, MHT.T_ambient, '-', ...
        'Color', 'w', 'DisplayName', 'ambient')
end

title('Tunnel temperatures (\pm0.03 K)')
xlabel('time (s)')
ylabel('temperature (\circC)')
legend('Location', 'NEO');

% -------------------------------------------------------------------------
%   Chiller temperatures
% -------------------------------------------------------------------------

h1c = subplot(3, 2, 5);
plot(MHT.time, MHT.T_chill_setp, '-', 'LineWidth', 4, ...
     'Color', cm(5, :), 'DisplayName', 'setp.')
hold on
plot(MHT.time, MHT.T_chill, '-', ...
     'Color', cm(3, :), 'DisplayName', 'chiller')

title('Chiller temperatures (\pm0.1 K)')
xlabel('time (s)')
ylabel('temperature (\circC)')
legend('Location', 'NEO');

% -------------------------------------------------------------------------
%   Tunnel speed
% -------------------------------------------------------------------------

MHT.v_flow = MHT.Q_tunnel / MHT.constants.area_meas_section / 36.0; % [cm/s]
    
area_meas_section = sprintf('%.3f', MHT.constants.area_meas_section);
if MHT.constants.area_meas_section == 0.012
    area_meas_section = '0.3 x 0.04';
elseif MHT.constants.area_meas_section == 0.018
    area_meas_section = '0.3 x 0.06';
elseif MHT.constants.area_meas_section == 0.024
    area_meas_section = '0.3 x 0.08';
end

h1d = subplot(3, 2, 2);
plot(MHT.time, MHT.v_flow, '-', ...
     'Color', cm(6, :), 'DisplayName', 'v\_flow')
hold on

title(sprintf('Meas. section: %s m^2\nTunnel flow', area_meas_section))
xlabel('time (s)')
ylabel('flow speed (cm/s)')

% -------------------------------------------------------------------------
%  PSU power
% -------------------------------------------------------------------------

h1e = subplot(3, 2, 4);
plot(MHT.time, MHT.P_PSU_1, '-', ...
     'Color', cm(6, :), 'DisplayName', '#1')
hold on
plot(MHT.time, MHT.P_PSU_2, '-', ...
     'Color', cm(4, :), 'DisplayName', '#2')
plot(MHT.time, MHT.P_PSU_3, '-', ...
     'Color', cm(2, :), 'DisplayName', '#3')
   
title('PSU power (\pm0.3 W)')
xlabel('time (s)')
ylabel('power (W)')
legend('Location', 'NEO');

% -------------------------------------------------------------------------
%  Gas volume fraction (GVF)
% -------------------------------------------------------------------------

MHT.GVF_pct = (MHT.Pdiff_GVF * 1e2 / MHT.constants.gravity / ...
               MHT.constants.GVF_porthole_distance / ...
               MHT.constants.density_liquid * 100);

h1f = subplot(3, 2, 6);
plot(MHT.time, MHT.GVF_pct, '-', ...
     'Color', cm(6, :), 'DisplayName', 'GVF\_pct')
hold on
   
title('Bubble injection')
xlabel('time (s)')
ylabel('gas vol. fraction (%)')

% -------------------------------------------------------------------------
%  Final make-up
% -------------------------------------------------------------------------

set(h1a, 'Position', [0.08, 0.71, 0.32, 0.22])
set(h1b, 'Position', [0.08, 0.39, 0.32, 0.22])
set(h1c, 'Position', [0.08, 0.07, 0.32, 0.22])
set(h1d, 'Position', [0.57, 0.71, 0.32, 0.22])
set(h1e, 'Position', [0.57, 0.39, 0.32, 0.22])
set(h1f, 'Position', [0.57, 0.07, 0.32, 0.22])

linkaxes([h1a h1b h1c h1d h1e h1f], 'x')
xlim(h1a, [MHT.time(1) MHT.time(end)])

DvG_layout_plots_style_dark(h1)

% Save to disk
MHT_saveFig(h1, [MHT.filename '_quickPlot'])

return