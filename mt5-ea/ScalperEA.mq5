#property strict
#include <Trade/Trade.mqh>

CTrade Trade;
input string IPC_URL = "http://127.0.0.1:8000/decide";
input bool   PAPER_MODE = true;        // if true, simulate fills & log only
input int    CooldownSec = 20;

datetime lastTradeTimeBySym[];
double dayStartEquity = 0;
double dayPnLPct = 0;

int OnInit() {
   ArrayResize(lastTradeTimeBySym, SymbolsTotal(false));
   dayStartEquity = AccountInfoDouble(ACCOUNT_EQUITY);
   Print("ScalperEA initialized. PaperMode=", PAPER_MODE);
   return(INIT_SUCCEEDED);
}

void OnDeinit(const int reason) { Print("ScalperEA deinit. reason=", reason); }

void OnTick() {
   string sym = _Symbol;
   MqlTick tick;
   if(!SymbolInfoTick(sym, tick)) return;

   // Basic symbol guards
   long tradeMode; SymbolInfoInteger(sym, SYMBOL_TRADE_MODE, tradeMode);
   if(tradeMode == SYMBOL_TRADE_MODE_DISABLED) return;

   // Collect quick market info
   double point = SymbolInfoDouble(sym, SYMBOL_POINT);
   double spread_points = (tick.ask - tick.bid)/point;
   double freeze_level = SymbolInfoInteger(sym, SYMBOL_TRADE_FREEZE_LEVEL);
   double tickvalue = SymbolInfoDouble(sym, SYMBOL_TRADE_TICK_VALUE);
   double lot_step = SymbolInfoDouble(sym, SYMBOL_VOLUME_STEP);
   double min_lot = SymbolInfoDouble(sym, SYMBOL_VOLUME_MIN);
   int digits = (int)SymbolInfoInteger(sym, SYMBOL_DIGITS);
   double equity = AccountInfoDouble(ACCOUNT_EQUITY);

   // Assemble small buffers for ticks (recent 2-3s) and 1m bars
   MqlRates rates[];
   int copied = CopyRates(sym, PERIOD_M1, 0, 200, rates);
   if(copied <= 20) return;

   // Serialize minimal payload (we keep it light)
   string body = "{";
   body += "\"symbol\":\""+sym+"\",";
   body += "\"tick_info\":{";
   body += "\"bid\":"+DoubleToString(tick.bid, digits)+",";
   body += "\"ask\":"+DoubleToString(tick.ask, digits)+",";
   body += "\"spread_points\":"+IntegerToString((int)spread_points)+",";
   body += "\"slippage_points\":5,";
   body += "\"point_size\":"+DoubleToString(point, 10)+",";
   body += "\"tick_value_per_lot\":"+DoubleToString(tickvalue, 10)+",";
   body += "\"equity_usd\":"+DoubleToString(equity, 2)+",";
   body += "\"ts_ms\":"+LongToString((long)(GetMicrosecondCount()/1000));
   body += "},";

   // Ticks: use last N book ticks as pseudo; here we emulate from MqlTick stream (bid/ask only)
   body += "\"ticks\":[";
   for(int i=0;i<25;i++){
      if(i>0) body+=",";
      body += "["+LongToString((long)(GetMicrosecondCount()/1000))+","+DoubleToString(tick.bid,digits)+","+DoubleToString(tick.ask,digits)+",0]";
   }
   body += "],";

   // 1m bars
   body += "\"bars_1m\":[";
   bool first=true;
   for(int i=ArraySize(rates)-100;i<ArraySize(rates);i++){
      if(i<0) continue;
      if(!first) body += ",";
      first=false;
      body += "["+LongToString((long)rates[i].time*1000)+","+DoubleToString(rates[i].open,digits)+","+DoubleToString(rates[i].high,digits)+","+DoubleToString(rates[i].low,digits)+","+DoubleToString(rates[i].close,digits)+","+DoubleToString(rates[i].tick_volume,0)+"]";
   }
   body += "],";

   // Risk state snapshot (EA owns authoritative daily PnL)
   double dayPnL = equity - dayStartEquity;
   dayPnLPct = (dayPnL / dayStartEquity) * 100.0;

   body += "\"state\":{";
   body += "\"day_pnl_pct\":"+DoubleToString(dayPnLPct,2)+",";
   body += "\"hit_rate_pct\":55,";
   body += "\"recent_trades\":0,";
   body += "\"open_positions\":"+IntegerToString(PositionsTotal())+",";
   body += "\"symbol_exposure_pct\":{}";
   body += "}";
   body += "}";

   // Call Python
   string headers; char data[], result[];
   int timeout = 200;
   StringToCharArray(body, data);
   int status = WebRequest("POST", IPC_URL, headers, timeout, data, result, NULL);
   if(status != 200) { Print("WebRequest failed status=", status); return; }

   string json = CharArrayToString(result);
   string action = json_value(json, "action");
   double lots = StrToDouble(json_value(json, "lots"));
   int tp_points = (int)StrToInteger(json_value(json, "tp_points"));
   int sl_points = (int)StrToInteger(json_value(json, "sl_points"));
   string reason = json_value(json, "reason");

   if(action=="flat" || lots<=0) return;

   int symIdx = symbol_index(sym);
   datetime now = TimeCurrent();
   if(lastTradeTimeBySym[symIdx]!=0 && (now - lastTradeTimeBySym[symIdx]) < CooldownSec) return;

   if(spread_points > 100) return;

   double price = (action=="buy") ? tick.ask : tick.bid;
   double sl = (action=="buy") ? price - sl_points*point : price + sl_points*point;
   double tp = (action=="buy") ? price + tp_points*point : price - tp_points*point;

   MqlTradeRequest req; MqlTradeResult res; ZeroMemory(req); ZeroMemory(res);
   req.action = TRADE_ACTION_DEAL;
   req.symbol = sym;
   req.volume = normalize_volume(lots, min_lot, lot_step);
   req.type = (action=="buy") ? ORDER_TYPE_BUY : ORDER_TYPE_SELL;
   req.price = price;
   req.sl = sl;
   req.tp = tp;
   req.deviation = 5;
   req.type_filling = ORDER_FILLING_IOC;

   if(PAPER_MODE){
      Print("PAPER ", sym, " ", action, " lots=", req.volume, " tp_pts=", tp_points, " sl_pts=", sl_points, " reason=", reason);
      lastTradeTimeBySym[symIdx] = now;
      return;
   }

   if(!OrderSend(req, res)){
      Print("OrderSend failed: ", GetLastError());
      return;
   }
   if(res.retcode == TRADE_RETCODE_DONE){
      Print("LIVE ", sym, " ", action, " lots=", req.volume, " price=", DoubleToString(price,digits), " tp=", DoubleToString(tp,digits), " sl=", DoubleToString(sl,digits));
      lastTradeTimeBySym[symIdx] = now;
   } else {
      Print("OrderSend retcode=", res.retcode);
   }
}

string json_value(string json, string key){
   string pat = "\"" + key + "\":";
   int p = StringFind(json, pat, 0);
   if(p<0) return "";
   int start = p + StringLen(pat);
   int end = StringFind(json, ",", start);
   int brace = StringFind(json, "}", start);
   if(end<0 || (brace>0 && brace<end)) end = brace;
   string raw = StringSubstr(json, start, end-start);
   raw = StringTrimLeft(StringTrimRight(raw));
   if(StringGetCharacter(raw,0)=='\"') raw = StringSubstr(raw,1, StringLen(raw)-2);
   return raw;
}

double normalize_volume(double v, double min_lot, double step){
   if(v < min_lot) v = min_lot;
   double steps = MathFloor(v/step);
   return steps*step;
}

int symbol_index(string s){
   for(int i=0;i<SymbolsTotal(false);i++){
      string si = SymbolName(i, false);
      if(si==s) return i;
   }
   return 0;
}
