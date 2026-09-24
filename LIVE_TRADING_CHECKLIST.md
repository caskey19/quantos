# Live trading checklist

Every line ships false in `config/live_authorization.yml`. The application will not check these boxes. Edit that file yourself only after the corresponding evidence exists. Even a fully true file does not send live orders in this version: `build_broker` refuses to construct a live client.

- [ ] Data integrity validated on a market dataset
- [ ] Backtest validated under the stress model
- [ ] Look-ahead audit passed
- [ ] Survivorship review passed
- [ ] Transaction costs modeled
- [ ] Slippage modeled
- [ ] Walk-forward validation passed
- [ ] Final holdout evaluated once, at a promotion review
- [ ] Paper trading completed on the same order path
- [ ] Shadow mode completed against real quotes
- [ ] Risk engine tests passed
- [ ] Kill switch tested
- [ ] Broker reconciliation tested
- [ ] Duplicate order protection tested
- [ ] Restart recovery tested
- [ ] Market data disconnect tested
- [ ] Broker disconnect tested
- [ ] Logging verified
- [ ] Monitoring verified
- [ ] Alerts verified
- [ ] Security review completed
- [ ] Credentials isolated
- [ ] Position limits configured
- [ ] Daily loss limit configured
- [ ] Capital limit configured
- [ ] Manual live authorization received

Limited-live caps in the same file are zero. They do not increase themselves.
