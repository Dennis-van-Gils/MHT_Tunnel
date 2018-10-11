function MHT = MHT_readFile(fn, prevent_LP_filter)
% Reads in a log file acquired with the Python MHT Tunnel Control program.
% A 2nd order Butterworth low-pass filter with a cut-off frequency of
% 0.1 Hz and zero-phase distortion will be applied to all sensor
% timeseries. Validated.
%
% Args:
%    fn (string, optional):
%       Filename of the log to be read. When omitted, the user will be
%       promted to browse to the file.
%    prevent_LP_filter (boolean, optional, default=false):
%       Prevent the low-pass filter from being applied. Use only for
%       debugging this function and investigating proper LP settings.
%
% Returns:
%    MHT structure: containing header information and timeseries fields
%
% Dennis van Gils
% 11-10-2018

% -------------------------------------------------------------------------
%   Check input arguments
% -------------------------------------------------------------------------  

if nargin < 1
  prevent_LP_filter = false;
end

fPrompt = 0;
if nargin == 0
  fPrompt = 1;
else
  if isempty(fn)
    fPrompt = 1;
  end
end

if fPrompt
   % Prompt the user to browse to the file to read
  [fn, pathName] = uigetfile({'*.txt'; '*.*'}, 'Select .txt file');

  if fn == 0
    disp('User pressed cancel.')
    if nargout
      MHT = 0;
    end
    return
  else
    fn = fullfile(pathName, fn);
  end
end

% -------------------------------------------------------------------------
%   Parse data file and create output structure
% -------------------------------------------------------------------------

% Predefine header constants
constants.gravity = nan;
constants.area_meas_section = nan;
constants.GVF_porthole_distance = nan;
constants.density_liquid = nan;

f = fopen(fn, 'r', 'n', 'UTF-8');

% Scan the first lines for the start of the header and data sections
MAX_LINES = 100; % Stop scanning after this number of lines
strHeader = cell(0);
success = false;
for iLine = 1:MAX_LINES
  strLine = fgetl(f);
  if strcmpi(strLine, '[HEADER]')
    % Simply skip
  elseif strcmpi(strLine, '[DATA]')
    % Found data section. Exit loop.
    iLineData = iLine;  
    success = true;
    break
  else
    % We must be in the header section now
    strHeader{end + 1, 1} = strLine;                                        %#ok<AGROW>
    % Parse info out of the header
    if strfind(strLine, 'Gravity [m2/s]:') == 1
      parts = strsplit(strLine, ':');
      constants.gravity = str2double(parts{end});
    end
    if strfind(strLine, 'Area meas. section [m2]:') == 1
      parts = strsplit(strLine, ':');
      constants.area_meas_section = str2double(parts{end});
    end
    if strfind(strLine, 'GVF porthole distance [m]:') == 1
      parts = strsplit(strLine, ':');
      constants.GVF_porthole_distance = str2double(parts{end});
    end
    if strfind(strLine, 'Density liquid [kg/m3]:') == 1
      parts = strsplit(strLine, ':');
      constants.density_liquid = str2double(parts{end});
    end
  end
end

if not(success)
   fprintf('Incorrect file format. Could not find [DATA] section.\n')
   return
end

% The line after [DATA] contains the units of the data columns
strUnits = fgetl(f);
strUnits = textscan(strUnits, '%s', 'Delimiter', '\t');
strUnits = strUnits{1};
strUnits = strrep(strUnits, '[', '');
strUnits = strrep(strUnits, ']', '');

% The next line contains the names of the data columns
strNames = fgetl(f);
strNames = textscan(strNames, '%s', 'Delimiter', '\t');
strNames = strNames{1};

fclose(f);

% Read in all data columns including column names
tmp_table = readtable(fn, 'Delimiter', '\t', 'HeaderLines', iLineData + 1);

% Transform to final structure
MHT = table2struct(tmp_table, 'ToScalar', true);

% Add extra fields
[folder, filename, extension] = fileparts(fn);                              %#ok<NASGU,ASGLU>
MHT.filename = filename;
iTmp = regexp(fn, '\d\d\d\d\d\d_\d\d\d\d\d\d');
MHT.DAQ_date  = fn(iTmp:iTmp+5);
MHT.DAQ_time  = fn(iTmp+7:iTmp+12);
MHT.header    = strHeader;
MHT.constants = constants;
MHT.units     = horzcat(strNames, strUnits);

% Reorder fields
nFields = length(fieldnames(MHT));
MHT = orderfields(MHT, [nFields-5:nFields 1:nFields-6]);

% Apply low-pass filtering to specific timeseries
if not(prevent_LP_filter)
  f_s = 1/mean(diff(MHT.time)); % Original sampling frequency [Hz]
  f3dB_LP = 0.1;                % Low-pass cut-off frequency: 0.1 [Hz]
  [filt_b, filt_a] = butter(2, f3dB_LP / (f_s/2), 'low');

  fields = fieldnames(MHT);
  for iField = 1:nFields
    strField = fields{iField};
    if (strcmpi(strField , 'Q_tunnel') || ...
        strcmpi(strField , 'Q_bubbles') || ...
        strcmpi(strField , 'Pdiff_GVF') || ...
        strncmpi(strField, 'T_TC_', 5) || ...
        strcmpi(strField , 'T_ambient') || ...
        strcmpi(strField , 'T_inlet') || ...
        strcmpi(strField , 'T_outlet') || ...
        strcmpi(strField , 'T_chill') || ...
        strncmpi(strField, 'P_PSU_', 6))
      MHT.(strField) = filtfilt(filt_b, filt_a, MHT.(strField));
    end
  end
end

% Snippets to use the wall time in Matlab plots
%   a=datenum(MHT.wall_time, 'HH:MM:SS.FFF');
%   plot(a, MHT.T_TC_01)
%   datetick('x', 'HH:MM:SS')
%   datestr(a(1), 'HH:MM:SS.FFF')
